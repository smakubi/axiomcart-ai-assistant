"""Transport-independent teaching engine: 24 kHz mono int16 PCM, 20 ms frames.

Energy detection is deliberately simple. Use headphones; this is not acoustic
 echo cancellation or a production speech detector. No conversation memory.
"""

import asyncio
import contextlib
import io
import math
import os
import time
import wave
from collections import deque

import numpy as np

RATE = 24000
FRAME_MS = 20
FRAME_BYTES = 960


class TurnCapture:
    """Bounded pre-roll, 120 ms sound confirmation, silence endpoint, hard cap."""

    def __init__(self, threshold=0.025, silence_ms=700, max_ms=15000):
        if not 0 < threshold < 1 or not 20 <= silence_ms <= 5000 or max_ms < 120:
            raise ValueError("Use threshold 0..1, silence 20..5000 ms, max >=120 ms.")
        self.threshold = threshold
        self.quiet_limit = math.ceil(silence_ms / FRAME_MS)
        self.max_frames = math.ceil(max_ms / FRAME_MS)
        self.reset()

    def reset(self):
        self.preroll = deque(maxlen=10)
        self.frames = []
        self.loud = self.quiet = 0
        self.active = False

    def feed(self, pcm):
        if len(pcm) != FRAME_BYTES:
            raise ValueError("Expected 960 bytes of 24 kHz mono int16 PCM.")
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        loud = float(np.sqrt(np.mean(samples * samples))) > self.threshold
        started = False
        if not self.active:
            self.preroll.append(pcm)
            self.loud = self.loud + 1 if loud else 0
            if self.loud < 6:
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

    def __init__(self, backend, sink, barge_in=True, **capture_options):
        self.backend, self.sink, self.barge_in = backend, sink, barge_in
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
        started, audio = self.capture.feed(pcm)
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
            await self.sink.write(epoch, pcm)

        try:
            await self.backend.reply(audio, emit, status)
            await self.sink.drain(epoch)
            if epoch == self.epoch:
                await self.sink.event({"type": "reply_done", "epoch": epoch})
        except asyncio.CancelledError:
            raise
        except Exception as error:
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
    """Batch STT/LLM and streamed TTS; async requests allow local cancellation."""

    def __init__(self, client):
        self.client = client

    async def reply(self, pcm, emit, status):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(pcm)
        transcription = await self.client.audio.transcriptions.create(
            model=os.getenv("VOICE_STT_MODEL", "gpt-4o-mini-transcribe"),
            file=("turn.wav", buffer.getvalue(), "audio/wav"),
        )
        text = transcription.text.strip()
        await status("transcript", text)
        if not text:
            return
        result = await self.client.responses.create(
            model=os.getenv("VOICE_LLM_MODEL", "gpt-4.1-mini"),
            instructions="You are a helpful shopping assistant. Reply in 1-3 sentences.",
            input=text,
            max_output_tokens=200,
        )
        answer = result.output_text.strip()
        await status("answer", answer)
        if not answer:
            return
        pending = b""
        async with self.client.audio.speech.with_streaming_response.create(
            model=os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("VOICE_TTS_VOICE", "marin"),
            input=answer,
            response_format="pcm",
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=FRAME_BYTES):
                pending += chunk
                while len(pending) >= FRAME_BYTES:
                    await emit(pending[:FRAME_BYTES])
                    pending = pending[FRAME_BYTES:]
            if len(pending) % 2:
                raise RuntimeError("Incomplete PCM sample.")
            if pending:
                await emit(pending.ljust(FRAME_BYTES, b"\0"))


class DemoBackend:
    """Offline diagnostic: responds with a quiet tone, never calls an API."""

    async def reply(self, pcm, emit, status):
        await status("transcript", "[offline: microphone turn detected, no STT]")
        await status("answer", "[offline: three-second tone, interrupt with speech]")
        t = np.arange(480) / RATE
        tone = (np.sin(2 * np.pi * 400 * t) * 2000).astype("<i2").tobytes()
        for _ in range(150):
            await emit(tone)
