"""Concurrent local capture/playback. API calls never run in audio callbacks."""

import asyncio
import queue
import threading
import time

import numpy as np
import sounddevice as sd
from live_core import RATE, DemoBackend, LiveSession, OpenAIBackend, SpeechVAD
from openai import AsyncOpenAI


class SpeakerBuffer:
    def __init__(self):
        self.queue = queue.Queue(maxsize=25)  # At most 500 ms queued.
        self.lock = threading.Lock()
        self.epoch = 0
        self.until = 0
        self.latency = 0.1
        self.underflows = 0
        self.started = self.flushing = False

    def reset(self, epoch):
        with self.lock:
            self.epoch = epoch
            while not self.queue.empty():
                self.queue.get_nowait()
            self.until = 0
            self.started = self.flushing = False

    def put(self, epoch, pcm):
        with self.lock:
            if epoch == self.epoch:
                self.queue.put_nowait(pcm)

    def callback(self, outdata, frames, timing, status):
        outdata.fill(0)
        with self.lock:
            if status:
                self.underflows += 1
            if not self.started and (self.queue.qsize() >= 6 or self.flushing):
                self.started = True
            if not self.started:
                return
            try:
                pcm = self.queue.get_nowait()
            except queue.Empty:
                if not self.flushing:
                    self.started = False
                    self.underflows += 1
                return
            samples = np.frombuffer(pcm, dtype="<i2")
            outdata[: len(samples), 0] = samples
            self.until = time.monotonic() + self.latency + frames / RATE


class NativeSink:
    def __init__(self):
        self.speaker = SpeakerBuffer()

    async def event(self, event):
        kind = event["type"]
        if kind == "speech_start":
            print(
                "Interrupted; old reply discarded."
                if event["interrupted"]
                else "Speech detected; microphone remains active."
            )
        elif kind == "first_audio":
            print(f"First audio queued after end of turn: {event['ms']} ms")
        else:
            print(f"{kind}: {event.get('text', '')}")

    async def reset(self, epoch):
        self.speaker.reset(epoch)

    async def write(self, epoch, pcm):
        while epoch == self.speaker.epoch:
            try:
                self.speaker.put(epoch, pcm)
                return
            except queue.Full:
                await asyncio.sleep(0.005)

    async def drain(self, epoch):
        self.speaker.flushing = True
        while epoch == self.speaker.epoch:
            if self.speaker.queue.empty() and time.monotonic() >= self.speaker.until:
                return
            await asyncio.sleep(0.01)


async def run_native(args):
    sink = NativeSink()
    microphone = queue.Queue(maxsize=50)  # Bound stalled capture to one second.
    overflow = threading.Event()

    def capture(indata, frames, timing, status):
        if status:
            overflow.set()
        try:
            microphone.put_nowait(indata[:, 0].astype("<i2").tobytes())
        except queue.Full:
            overflow.set()

    client = None if args.offline else AsyncOpenAI(timeout=30, max_retries=0)
    backend = DemoBackend() if args.offline else OpenAIBackend(client)
    session = LiveSession(
        backend,
        sink,
        barge_in=args.stage == "barge-in",
        threshold=args.threshold,
        silence_ms=args.silence_ms,
        speech_detector=None if args.offline else SpeechVAD(),
        confirm_ms=120 if args.offline else 240,
        interrupt_ms=120 if args.offline else 500,
    )
    print("Use HEADPHONES. Ctrl+C to stop. Microphone stays active during playback.")
    print("Offline tone diagnostic." if args.offline else "Assistant voice is AI-generated.")
    try:
        with sd.OutputStream(
            samplerate=RATE,
            channels=1,
            dtype="int16",
            blocksize=480,
            callback=sink.speaker.callback,
        ) as output:
            sink.speaker.latency = output.latency
            with sd.InputStream(
                samplerate=RATE, channels=1, dtype="int16", blocksize=480, callback=capture
            ):
                while True:
                    if overflow.is_set():
                        raise RuntimeError("Microphone overflow; restart and reduce system load.")
                    try:
                        pcm = microphone.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.005)
                        continue
                    await session.feed(pcm)
    finally:
        await session.close()
        if client is not None:
            await client.close()
        if sink.speaker.underflows:
            print(f"Speaker callback warnings: {sink.speaker.underflows}")
