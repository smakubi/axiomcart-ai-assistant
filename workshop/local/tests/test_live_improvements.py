import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest
from live_core import EchoGuard, LiveSession, OpenAIBackend, TextChunks


def test_text_chunks_start_early_without_splitting_words():
    chunker = TextChunks()
    assert chunker.feed("I can help you find shoes. ") == ["I can help you find shoes."]
    assert chunker.feed("They cost $49.95 and ") == []
    assert chunker.feed("come in blue.") == []
    assert chunker.finish() == "They cost $49.95 and come in blue."


def test_echo_reference_rejects_delayed_playback_but_keeps_other_speech():
    guard = EchoGuard()
    t = np.arange(480 * 12) / 24000
    signal = (np.sin(2 * np.pi * (180 * t + 300 * t * t)) * 6000).astype("<i2")
    for frame in np.split(signal, 12):
        guard.add(frame.tobytes())
    assert guard.matches((signal[230:710] // 3).astype("<i2").tobytes())
    different = (np.sin(2 * np.pi * 700 * np.arange(480) / 24000) * 6000).astype("<i2")
    assert not guard.matches(different.tobytes())


@pytest.mark.asyncio
async def test_first_tts_starts_before_llm_finishes_and_cancellation_closes_streams():
    first_tts, release_llm, closed = asyncio.Event(), asyncio.Event(), []
    requests, frames = [], []

    class Events:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append("llm")

        def __aiter__(self):
            return self.iterate()

        async def iterate(self):
            yield SimpleNamespace(
                type="response.output_text.delta", delta="Here are some walking shoes. "
            )
            await release_llm.wait()
            yield SimpleNamespace(type="response.output_text.delta", delta="They are comfortable.")
            yield SimpleNamespace(type="response.completed")

    class Audio:
        async def iter_bytes(self, chunk_size):
            yield bytes(960)
            await asyncio.Event().wait()

    @asynccontextmanager
    async def tts(**kwargs):
        requests.append(kwargs["input"])
        first_tts.set()
        try:
            yield Audio()
        finally:
            closed.append("tts")

    client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(return_value=SimpleNamespace(text="Shoes"))
            ),
            speech=SimpleNamespace(with_streaming_response=SimpleNamespace(create=tts)),
        ),
        responses=SimpleNamespace(create=AsyncMock(return_value=Events())),
    )

    async def emit(pcm):
        frames.append(pcm)

    async def status(*args):
        pass

    task = asyncio.create_task(OpenAIBackend(client).reply(bytes(960), emit, status))
    await asyncio.wait_for(first_tts.wait(), 1)
    assert not release_llm.is_set()
    assert requests == ["Here are some walking shoes."]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sorted(closed) == ["llm", "tts"]
    assert client.responses.create.call_args.kwargs["stream"] is True


@pytest.mark.asyncio
async def test_busy_session_requires_longer_confirmed_speech():
    from test_live_core import QUIET, SPEECH, Backend, Sink

    sink, backend = Sink(), Backend()
    session = LiveSession(backend, sink, silence_ms=40, interrupt_ms=500)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)
    for _ in range(10):
        await session.feed(SPEECH)
    assert not backend.cancelled.is_set()
    for _ in range(15):
        await session.feed(SPEECH)
    await asyncio.sleep(0)
    assert backend.cancelled.is_set()
    await session.close()


def test_real_speech_classifier_rejects_silence():
    from live_core import SpeechVAD

    vad = SpeechVAD()
    for _ in range(20):
        assert not vad(bytes(960))


@pytest.mark.asyncio
async def test_rtc_buffers_six_frames_before_playing_and_resets_on_cancel():
    from transport_server import RTCSink

    sink = RTCSink()
    for _ in range(5):
        await sink.write(0, bytes([5, 0]) * 480)
    assert not (await sink.track.recv()).to_ndarray().any()
    await sink.write(0, bytes([5, 0]) * 480)
    assert ((await sink.track.recv()).to_ndarray() == 5).all()
    await sink.reset(1)
    assert not (await sink.track.recv()).to_ndarray().any()
    await sink.close()


def test_first_clause_has_a_shorter_latency_budget_and_decimals_survive_split_deltas():
    chunks = TextChunks()
    parts = chunks.feed("I can suggest comfortable walking shoes for your daily commute and ")
    assert parts and len(parts[0]) < 60
    decimal = TextChunks()
    assert decimal.feed("The price is $49.") == []
    assert decimal.feed("95. ") == ["The price is $49.95."]


def test_live_speech_confirmation_tolerates_quiet_consonants_but_rejects_clicks():
    from live_core import TurnCapture

    speech = np.full(480, 9000, dtype="<i2").tobytes()
    capture = TurnCapture(speech_detector=lambda pcm: True, confirm_ms=500)
    events = [capture.feed(frame)[0] for frame in ([speech] * 7 + [bytes(960)]) * 3 + [speech] * 2]
    assert any(events)
    clicks = TurnCapture(speech_detector=lambda pcm: True, confirm_ms=500)
    assert not any(clicks.feed(frame)[0] for frame in ([speech] + [bytes(960)] * 4) * 20)
