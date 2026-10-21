# Exercises 3–7 — Build the voice cascade, one reason at a time

Use [local/README.md](local/README.md) for setup and runnable commands. Each exercise uses `workshop/local/voice.py`.

## 3 — Why do we need an LLM between STT and TTS?
**Predict:** If a customer says "Show me shoes under $100," can STT decide which products to recommend? No: transcription maps sound to words, not words to actions.

Run `python voice.py llm --text "Show me running shoes under $100"`. Read `think()`. Ask what the model receives and returns. This is deliberately a simple text-only LLM, not LangGraph. The current workshop model is not connected to a real catalog: do not treat invented product recommendations as actual inventory.

## 4 — Why is TTS separate?
**Predict:** Can we play the LLM's returned string directly through speakers? No: speakers need a time-varying signal.

Run `python voice.py tts --text "Welcome to AxiomCart"`. Read `speak()` and `play_wav()`. Explain: text → synthesis service → WAV bytes → PCM samples → audio device. A WAV file is a container; the PCM samples are the waveform.

## 5 — Why does the cascade feel slow?
Run `python voice.py cascade`. Ask students to identify every waiting point: fixed recording, upload/transcription, LLM completion, TTS generation, and playback. The printed TTS time includes playback: do not call it pure synthesis latency. Have learners propose a way to separately measure synthesis completion and first audible sample.

## 6 — How does the assistant know the customer finished?
Run `python voice.py vad --silence-ms 200`, then `python voice.py vad --silence-ms 1200`. Ask: which prematurely cuts a hesitant speaker? Which feels slower? Read `SilenceDetector.update()`. This is energy-threshold silence detection, not semantic turn-taking or a trained VAD.

## 7 — Why is the basic loop not full duplex?
Run `python voice.py loop`. The microphone is active while recording, then stops while STT, LLM, and TTS run. The assistant cannot hear an interruption during playback. Ask students to design two simultaneous tasks: an input monitor and an output player, coordinated by a cancellation signal. Discuss echo cancellation and false interruptions before attempting implementation.

## Extension — Compare with AxiomCart's actual streaming system
Open `src/voice.py`, `src/speech_api.py`, and `public/assets/live-transcription.mjs`. AxiomCart uses a browser microphone/WebRTC for live STT and streams PCM from Python for TTS. The local CLI is deliberately simpler; it is **not** an equivalent real-time implementation.

### Questions for the end of coaching
1. What is the difference between sound, audio samples, and text?
2. Why doesn't an LLM need to know whether input came from a keyboard or STT?
3. Why does a silence threshold sometimes cut off a sentence?
4. Why does streaming TTS require a player that can consume chunks as they arrive?
5. What has to run concurrently to support barge-in?

### Teaching rhythm
Ask → predict → run → observe → explain → change one parameter → run again. Never introduce five new abstractions before the learner has tested one.
