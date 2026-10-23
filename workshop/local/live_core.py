"""Transport-independent teaching engine: 24 kHz mono int16 PCM, 20 ms frames.

Live input uses a speech classifier plus playback-reference rejection; diagnostic
mode retains an energy gate. Browser AEC or native headphones are still needed.
No conversation memory or live search is provided.
"""

import asyncio
import contextlib
import io
import math
import os
import re
import time
import wave
from collections import deque

import numpy as np

RATE = 24000
FRAME_MS = 20
FRAME_BYTES = 960


class SpeechVAD:
    """WebRTC speech classification at 16 kHz; this is notecho cancellation."""

    def __init__(self):
        import webrtcvad

        self.vad = webrtcvad.Vad(3)
        self.positions = np.arange(320) * 1.5

    def __call__(self, pcm):
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
        # Low-pass before converting 24 kHz to the detector's supported 16 kHz.
        filtered = np.convolve(
            np.pad(samples, (1, 1), mode="edge"), [0.25, 0.5, 0.25], mode="valid"
        )
        converted = np.interp(self.positions, np.arange(480), filtered).astype("<i2")
        return self.vad.is_speech(converted.tobytes(), 16000)


class EchoGuard:
    """Reject strongly correlated playback leakage, retaining two seconds of reference.

    This supplements browser AEC; it cannot replace an acoustic echo canceller.
    Correlation falls during different user speech, permitting double talk.
    """

    def __init__(self):
        self.frames = deque(maxlen=100)
        self.updated = 0

    def add(self, pcm):
        self.frames.append(np.frombuffer(pcm, dtype="<i2")[::3].astype(np.float32))
        self.updated = time.monotonic()

    def matches(self, pcm):
        if not self.frames or time.monotonic() - self.updated > 2:
            return False
        current = np.frombuffer(pcm, dtype="<i2")[::3].astype(np.float32)
        current -= current.mean()
        energy = float(current @ current)
        if energy < 160 * 25:
            return False
        reference = np.concatenate(self.frames)
        n = len(current)
        if len(reference) < n:
            return False
        sums = np.r_[0, np.cumsum(reference, dtype=np.float64)]
        squares = np.r_[0, np.cumsum(reference * reference, dtype=np.float64)]
        variance = squares[n:] - squares[:-n] - (sums[n:] - sums[:-n]) ** 2 / n
        correlation = np.abs(np.correlate(reference, current, mode="valid"))
        scores = correlation / np.sqrt(np.maximum(variance, 1) * energy)
        best = int(scores.argmax())
        return bool(scores[best] > 0.78 and energy <= variance[best] * 2.25)


class TextChunks:
    """Emit a first sentence/clause early, then bounded speakable text segments."""

    def __init__(self):
        self.pending = ""
        self.first = True

    def feed(self, delta):
        self.pending += delta
        result = []
        while self.pending:
            # A period inside a decimal/abbreviation is not followed by a space.
            boundary = re.search(r"[!?;](?=\s|$)|\.(?=\s)", self.pending)
            end = boundary.end() if boundary else 0
            limit = 60 if self.first else 140
            if not end and len(self.pending) >= limit:
                end = self.pending.rfind(" ", 25, limit)
                if end < 0 and len(self.pending) >= 240:
                    end = len(self.pending)
            if end <= 0:
                break
            part, self.pending = self.pending[:end].strip(), self.pending[end:].lstrip()
            if part:
                self.first = False
                result.append(part)
        return result

    def finish(self):
        result, self.pending = self.pending.strip(), ""
        return result


class TurnCapture:
    """Bounded pre-roll, 120 ms sound confirmation, silence endpoint, hard cap."""

    def __init__(
        self,
        threshold=0.025,
        silence_ms=700,
        max_ms=15000,
        speech_detector=None,
        confirm_ms=120,
        preroll_frames=10,
    ):
        if not 0 < threshold < 1 or not 20 <= silence_ms <= 5000 or max_ms < 120:
            raise ValueError("Use threshold 0..1, silence 20..5000 ms, max >=120 ms.")
        self.speech_detector = speech_detector
        self.confirm_ms = confirm_ms
        self.preroll_frames = preroll_frames
        self.threshold = threshold
        self.quiet_limit = math.ceil(silence_ms / FRAME_MS)
        self.max_frames = math.ceil(max_ms / FRAME_MS)
        self.reset()

    def reset(self):
        self.preroll = deque(maxlen=self.preroll_frames)
        self.frames = []
        self.votes = deque(maxlen=250)
        self.loud = self.quiet = 0
        self.active = False

    def feed(self, pcm, confirm_ms=None):
        if len(pcm) != FRAME_BYTES:
            raise ValueError("Expected 960 bytes of 24 kHz mono int16 PCM.")
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        loud = float(np.sqrt(np.mean(samples * samples))) > self.threshold
        if self.speech_detector is not None:
            loud = self.speech_detector(pcm) and loud
        started = False
        if not self.active:
            self.preroll.append(pcm)
            self.loud = self.loud + 1 if loud else 0
            needed = math.ceil((confirm_ms or self.confirm_ms) / FRAME_MS)
            self.votes.append(loud)
            if self.speech_detector is None:
                confirmed = self.loud >= needed
            else:
                votes = list(self.votes)[-needed:]
                confirmed = loud and len(votes) == needed and sum(votes) >= math.ceil(needed * 0.8)
            if not confirmed:
                return False, None
            self.active = started = True
            self.frames = list(self.preroll)
        else:
            self.frames.append(pcm)
        self.quiet = 0 if loud else self.quiet + 1
        if self.quiet >= self.quiet_limit or len(self.frames) >= self.max_frames:
            audio = b"".join(self.frames)
            self.reset()
            return started, audio
        return started, None


class LiveSession:
    """One bounded pending turn, cancellable reply, and epoch-based stale rejection."""

    def __init__(self, backend, sink, barge_in=True, interrupt_ms=120, **capture_options):
        self.backend, self.sink, self.barge_in = backend, sink, barge_in
        self.interrupt_ms = interrupt_ms
        self.echo = EchoGuard()
        capture_options.setdefault("preroll_frames", max(10, math.ceil(interrupt_ms / 20) + 5))
        self.capture = TurnCapture(**capture_options)
        self.epoch = 0
        self.task = None
        self.tasks = set()
        self.pending = None
        self.closed = False

    @property
    def busy(self):
        return self.task is not None and not self.task.done()

    async def invalidate(self):
        self.epoch += 1  # Invalidate before cancellation can race with another write.
        self.pending = None
        if self.busy:
            self.task.cancel()
        await self.sink.reset(self.epoch)

    async def feed(self, pcm):
        if self.closed:
            return
        if self.echo.matches(pcm):
            pcm = bytes(FRAME_BYTES)
        started, audio = self.capture.feed(
            pcm, confirm_ms=self.interrupt_ms if self.busy else self.capture.confirm_ms
        )
        if started:
            was_busy = self.busy
            if self.barge_in:
                await self.invalidate()
            await self.sink.event(
                {
                    "type": "speech_start",
                    "epoch": self.epoch,
                    "interrupted": was_busy and self.barge_in,
                }
            )
        if audio is not None:
            if self.busy and not self.barge_in:
                # Full duplex without barge-in: keep just the latest next turn.
                self.pending = audio
                await self.sink.event({"type": "queued_turn", "epoch": self.epoch})
            else:
                await self.start(audio)

    async def start(self, audio):
        await self.invalidate()
        if len(self.tasks) >= 4:
            raise RuntimeError("Previous requests are not cancelling; restart the session.")
        self.task = asyncio.create_task(self.respond(self.epoch, audio))
        self.tasks.add(self.task)
        self.task.add_done_callback(self.tasks.discard)

    async def respond(self, epoch, audio):
        started = time.perf_counter()
        first = True

        async def status(kind, text):
            if epoch == self.epoch:
                await self.sink.event({"type": kind, "text": text, "epoch": epoch})

        async def emit(pcm):
            nonlocal first
            if epoch != self.epoch or self.closed:
                return
            if first:
                first = False
                await self.sink.event(
                    {
                        "type": "first_audio",
                        "epoch": epoch,
                        "ms": round((time.perf_counter() - started) * 1000),
                    }
                )
            self.echo.add(pcm)
            await self.sink.write(epoch, pcm)

        try:
            await self.backend.reply(audio, emit, status)
            await self.sink.drain(epoch)
            if epoch == self.epoch:
                await self.sink.event({"type": "reply_done", "epoch": epoch})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            while isinstance(error, BaseExceptionGroup):
                error = error.exceptions[0]
            if epoch == self.epoch:
                with contextlib.suppress(Exception):
                    await self.sink.reset(epoch)
                    # Do not expose provider error bodies or credentials.
                    await self.sink.event(
                        {
                            "type": "error",
                            "epoch": epoch,
                            "text": f"{type(error).__name__}: reply failed; retry.",
                        }
                    )
        finally:
            if not self.closed and epoch == self.epoch and self.pending is not None:
                pending, self.pending = self.pending, None
                # Current task is finishing; don't cancel ourselves in start().
                self.task = None
                await self.start(pending)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(Exception):
            await self.invalidate()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()


class OpenAIBackend:
    """Batch STT, streamed LLM text, and overlapping streamed speech synthesis."""

    def __init__(self, client):
        self.client = client

    async def reply(self, pcm, emit, status):
        started = time.perf_counter()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(pcm)
        transcription = await self.client.audio.transcriptions.create(
            model=os.getenv("VOICE_STT_MODEL", "gpt-4o-mini-transcribe"),
            file=("turn.wav", buffer.getvalue(), "audio/wav"),
            **(
                {"language": os.getenv("VOICE_STT_LANGUAGE", "en")}
                if os.getenv("VOICE_STT_LANGUAGE", "en")
                else {}
            ),
        )
        text = transcription.text.strip()
        await status("transcript", text)
        if not text:
            return
        await status("timing", f"STT {round((time.perf_counter() - started) * 1000)} ms")
        text_queue = asyncio.Queue(maxsize=2)
        audio_queue = asyncio.Queue(maxsize=50)  # One second, bounded and cancelled together.

        async def generate():
            chunks = TextChunks()
            answer = ""
            first = True
            stream = await self.client.responses.create(
                model=os.getenv("VOICE_LLM_MODEL", "gpt-4.1-mini"),
                instructions=(
                    "You are a spoken shopping assistant. Reply in English in one sentence, "
                    "at most 35 words. "
                    "Your input is transcribed speech: acknowledge that you can receive it. "
                    "You have no live search, inventory, product databases, images, or current "
                    "news. Never claim to have consulted sources or know current officeholders. "
                    "For current facts, state that you cannot verify them. Use plain spoken text."
                ),
                input=text,
                max_output_tokens=160,
                stream=True,
            )
            async with stream:
                async for event in stream:
                    if event.type == "response.output_text.delta":
                        if first:
                            first = False
                            elapsed = round((time.perf_counter() - started) * 1000)
                            await status("timing", f"First LLM text {elapsed} ms after turn")
                        answer += event.delta
                        for part in chunks.feed(event.delta):
                            await text_queue.put(part)
                    elif event.type in ("error", "response.failed", "response.incomplete"):
                        raise RuntimeError("Text stream failed or was incomplete.")
            if tail := chunks.finish():
                await text_queue.put(tail)
            await status("answer", answer.strip())
            await text_queue.put(None)

        async def synthesize():
            while (part := await text_queue.get()) is not None:
                pending = b""
                await status("speaking_part", part)
                async with self.client.audio.speech.with_streaming_response.create(
                    model=os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts"),
                    voice=os.getenv("VOICE_TTS_VOICE", "marin"),
                    input=part,
                    response_format="pcm",
                ) as response:
                    async for chunk in response.iter_bytes(chunk_size=FRAME_BYTES):
                        pending += chunk
                        while len(pending) >= FRAME_BYTES:
                            await audio_queue.put(pending[:FRAME_BYTES])
                            pending = pending[FRAME_BYTES:]
                    if len(pending) % 2:
                        raise RuntimeError("Incomplete PCM sample.")
                    if pending:
                        await audio_queue.put(pending.ljust(FRAME_BYTES, b"\0"))
            await audio_queue.put(None)

        async def play():
            while (frame := await audio_queue.get()) is not None:
                await emit(frame)

        # One cancellation scope: no orphan LLM, TTS, or prefetched audio after barge-in.
        async with asyncio.TaskGroup() as group:
            group.create_task(generate())
            group.create_task(synthesize())
            group.create_task(play())


class DemoBackend:
    """Offline diagnostic: responds with a quiet tone, never calls an API."""

    async def reply(self, pcm, emit, status):
        await status("transcript", "[offline: microphone turn detected, no STT]")
        await status("answer", "[offline: three-second tone, interrupt with speech]")
        t = np.arange(480) / RATE
        tone = (np.sin(2 * np.pi * 400 * t) * 2000).astype("<i2").tobytes()
        for _ in range(150):
            await emit(tone)
