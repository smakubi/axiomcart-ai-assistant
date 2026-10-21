"""Local, Python-only teaching pipeline. Run: python voice.py --help.

The microphone/speaker are on the local computer, unlike AxiomCart's browser.
Inference calls use OpenAI APIs. No LangGraph or JavaScript required.
"""
import argparse
import os
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).with_name(".env"))
RATE = 16000
FRAME_MS = 30
CHANNELS = 1
SAMPLE_DTYPE = "int16"


def save_wav(path, samples, rate=RATE):
    samples = np.asarray(samples, dtype=np.int16).reshape(-1)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def record_fixed(seconds=5):
    """Simplest baseline: capture exactly N seconds, then stop."""
    print(f"Recording for {seconds:g} seconds...")
    audio = sd.rec(int(seconds * RATE), samplerate=RATE,
                   channels=CHANNELS, dtype=SAMPLE_DTYPE)
    sd.wait()
    return audio.reshape(-1)


def rms(samples):
    """Normalized signal energy; loudness is NOT the same as speech."""
    x = np.asarray(samples, dtype=np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


class SilenceDetector:
    """Tiny energy-based turn detector for teaching, not production VAD."""
    def __init__(self, threshold=0.025, silence_ms=700, max_ms=15000):
        self.threshold, self.silence_ms, self.max_ms = threshold, silence_ms, max_ms
        self.elapsed_ms = 0
        self.last_speech_ms = None

    def update(self, volume, frame_ms=FRAME_MS):
        self.elapsed_ms += frame_ms
        if volume > self.threshold:
            self.last_speech_ms = self.elapsed_ms
        if self.elapsed_ms >= self.max_ms:
            return True
        return (self.last_speech_ms is not None and
                self.elapsed_ms - self.last_speech_ms >= self.silence_ms)


def record_until_silence(threshold=0.025, silence_ms=700, max_seconds=15):
    """Capture microphone frames until quiet follows detected sound.

    Pre-roll retains a little audio before threshold crossing.
    """
    detector = SilenceDetector(threshold, silence_ms, int(max_seconds * 1000))
    frames = []
    print("Speak naturally. Stop speaking to finish...")
    blocksize = RATE * FRAME_MS // 1000
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                        blocksize=blocksize) as stream:
        while True:
            frame, overflowed = stream.read(blocksize)
            if overflowed:
                print("Warning: microphone input overflow")
            frames.append(frame.copy())
            if detector.update(rms(frame)):
                break
    if detector.last_speech_ms is None:
        raise RuntimeError("No sound detected. Try a lower --threshold.")
    return np.concatenate(frames).reshape(-1)


def transcribe(client, path):
    with open(path, "rb") as audio:
        result = client.audio.transcriptions.create(
            model=os.getenv("VOICE_STT_MODEL", "gpt-4o-mini-transcribe"),
            file=audio,
        )
    return result.text.strip()


def think(client, text):
    result = client.responses.create(
        model=os.getenv("VOICE_LLM_MODEL", "gpt-4.1-mini"),
        instructions="You are a concise, helpful shopping assistant. Reply in 1-2 sentences.",
        input=text,
    )
    return result.output_text.strip()


def speak(client, text, output="reply.wav"):
    with client.audio.speech.with_streaming_response.create(
        model=os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts"),
        voice=os.getenv("VOICE_TTS_VOICE", "marin"),
        input=text,
        response_format="wav",
    ) as response:
        response.stream_to_file(output)
    play_wav(output)


def play_wav(path):
    with wave.open(str(path), "rb") as f:
        rate = f.getframerate()
        channels = f.getnchannels()
        width = f.getsampwidth()
        if width != 2:
            raise ValueError("This teaching player expects 16-bit PCM WAV.")
        audio = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
    sd.play(audio.reshape(-1, channels), samplerate=rate)
    sd.wait()


def cascade(client, samples):
    save_wav("recording.wav", samples)
    start = time.perf_counter()
    text = transcribe(client, "recording.wav")
    stt_ms = round((time.perf_counter() - start) * 1000)
    print(f"You: {text} (STT {stt_ms} ms)")
    if not text:
        return
    start = time.perf_counter()
    answer = think(client, text)
    llm_ms = round((time.perf_counter() - start) * 1000)
    print(f"Assistant: {answer} (LLM {llm_ms} ms)")
    start = time.perf_counter()
    speak(client, answer)
    tts_playback_ms = round((time.perf_counter() - start) * 1000)
    print(f"TTS generation + playback: {tts_playback_ms} ms")
    print("Note: TTS timing includes playback, not just generation.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["record", "stt", "llm", "tts", "cascade", "vad", "loop"])
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--threshold", type=float, default=0.025)
    parser.add_argument("--silence-ms", type=int, default=700)
    parser.add_argument("--text", default="Hello! Welcome to AxiomCart.")
    args = parser.parse_args()
    if args.stage in ("record", "cascade"):
        samples = record_fixed(args.seconds)
        save_wav("recording.wav", samples)
        print("Saved recording.wav")
        if args.stage == "record":
            return
    if args.stage == "vad":
        samples = record_until_silence(args.threshold, args.silence_ms)
        save_wav("recording.wav", samples)
        print("Saved recording.wav")
        return
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in workshop/local/.env")
    client = OpenAI()
    if args.stage == "stt":
        print(transcribe(client, "recording.wav"))
    elif args.stage == "llm":
        print(think(client, args.text))
    elif args.stage == "tts":
        speak(client, args.text)
    elif args.stage == "cascade":
        cascade(client, samples)
    elif args.stage == "loop":
        print("Ctrl+C to stop. Assistant listens one turn at a time.")
        try:
            while True:
                samples = record_until_silence(args.threshold, args.silence_ms)
                cascade(client, samples)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
