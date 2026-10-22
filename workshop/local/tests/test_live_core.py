import asyncio

import numpy as np
import pytest
from live_core import LiveSession, TurnCapture

QUIET = bytes(960)
SPEECH = np.full(480, 9000, dtype="<i2").tobytes()


def test_turn_preserves_preroll_and_waits_for_confirmed_speech():
    capture = TurnCapture(silence_ms=200)
    for _ in range(12):
        assert capture.feed(QUIET) == (False, None)
    for _ in range(5):
        assert capture.feed(SPEECH) == (False, None)
    assert capture.feed(SPEECH) == (True, None)
    for _ in range(9):
        assert capture.feed(QUIET)[1] is None
    started, audio = capture.feed(QUIET)
    assert not started
    assert SPEECH * 6 in audio
    assert len(audio) <= 26 * 960
    assert capture.feed(QUIET) == (False, None)


def test_turn_has_a_hard_bound_and_rejects_wrong_frames():
    capture = TurnCapture(max_ms=200)
    turn = None
    for _ in range(10):
        _, turn = capture.feed(SPEECH)
    assert turn is not None
    with pytest.raises(ValueError):
        capture.feed(b"x")


class Sink:
    def __init__(self):
        self.events, self.audio, self.epoch = [], [], 0
        self.played = asyncio.Event()

    async def event(self, event):
        self.events.append(event)

    async def reset(self, epoch):
        self.epoch = epoch
        self.audio.clear()
        self.played.set()

    async def write(self, epoch, pcm):
        if epoch == self.epoch:
            self.audio.append(pcm)

    async def drain(self, epoch):
        await self.played.wait()


class Backend:
    def __init__(self):
        self.calls = []
        self.cancelled = asyncio.Event()

    async def reply(self, audio, emit, status):
        self.calls.append(audio)
        await status("transcript", "test words")
        try:
            await emit(SPEECH)
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


@pytest.mark.asyncio
async def test_barge_in_cancels_old_reply_and_preserves_correction():
    sink, backend = Sink(), Backend()
    session = LiveSession(backend, sink, barge_in=True, silence_ms=40)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)
    assert sink.audio
    old_epoch = session.epoch
    for _ in range(6):
        await session.feed(SPEECH)
    await asyncio.sleep(0)
    assert backend.cancelled.is_set()
    assert session.epoch > old_epoch
    assert not sink.audio
    for _ in range(2):
        await session.feed(QUIET)
    await asyncio.sleep(0)
    assert len(backend.calls) == 2
    assert SPEECH * 6 in backend.calls[1]
    await session.close()
    assert not session.tasks


@pytest.mark.asyncio
async def test_full_duplex_captures_without_cancelling_reply():
    sink, backend = Sink(), Backend()
    session = LiveSession(backend, sink, barge_in=False, silence_ms=40)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    assert not backend.cancelled.is_set()
    assert session.pending is not None
    assert any(e["type"] == "queued_turn" for e in sink.events)
    await session.close()
    assert backend.cancelled.is_set()


@pytest.mark.asyncio
async def test_failure_is_reported_and_next_turn_still_works():
    class Broken:
        async def reply(self, *args):
            raise RuntimeError("provider failed")

    sink = Sink()
    session = LiveSession(Broken(), sink, silence_ms=40)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)
    assert any(e["type"] == "error" for e in sink.events)
    await session.close()


@pytest.mark.asyncio
async def test_close_still_joins_cancelled_tasks_if_sink_disconnects():
    sink, backend = Sink(), Backend()
    session = LiveSession(backend, sink, silence_ms=40)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)

    async def disconnected(epoch):
        raise ConnectionError("socket closed")

    sink.reset = disconnected
    await session.close()
    assert not session.tasks
    assert backend.cancelled.is_set()


@pytest.mark.asyncio
async def test_async_backend_wav_format_and_chunk_reassembly():
    import io
    import wave
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from live_core import OpenAIBackend

    requests, frames, statuses = [], [], []

    class Response:
        async def iter_bytes(self, chunk_size):
            assert chunk_size == 960
            for chunk in [b"\x01", b"\x02" * 960, b"\x03"]:
                yield chunk

    @asynccontextmanager
    async def speech(**kwargs):
        requests.append(kwargs)
        yield Response()

    transcribe = AsyncMock(return_value=SimpleNamespace(text="Shoes"))
    client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=transcribe),
            speech=SimpleNamespace(with_streaming_response=SimpleNamespace(create=speech)),
        ),
        responses=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(output_text="Try walking shoes."))
        ),
    )

    async def emit(frame):
        frames.append(frame)

    async def status(kind, text):
        statuses.append((kind, text))

    await OpenAIBackend(client).reply(SPEECH, emit, status)
    file = transcribe.call_args.kwargs["file"]
    with wave.open(io.BytesIO(file[1])) as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.readframes(480) == SPEECH
    assert requests[0]["response_format"] == "pcm"
    assert len(frames) == 2 and all(len(frame) == 960 for frame in frames)
    assert b"".join(frames)[:962] == b"\x01" + b"\x02" * 960 + b"\x03"
    assert statuses == [("transcript", "Shoes"), ("answer", "Try walking shoes.")]


@pytest.mark.asyncio
async def test_duplex_queued_correction_runs_after_playback_finishes():
    class CompletedBackend:
        def __init__(self):
            self.calls = []

        async def reply(self, audio, emit, status):
            self.calls.append(audio)
            await emit(SPEECH)

    sink, backend = Sink(), CompletedBackend()
    session = LiveSession(backend, sink, barge_in=False, silence_ms=40)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    await asyncio.sleep(0)
    for frame in [SPEECH] * 6 + [QUIET] * 2:
        await session.feed(frame)
    assert len(backend.calls) == 1
    sink.played.set()
    for _ in range(6):
        await asyncio.sleep(0)
    assert len(backend.calls) == 2
    assert session.pending is None
    await session.close()
