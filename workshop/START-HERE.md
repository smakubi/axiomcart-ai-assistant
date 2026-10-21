# Voice Cascade Workshop
**Wednesday coaching · Python · Local**

Build a voice assistant from first principles. Each step follows **predict → run → observe → production lesson**.

## Setup

Python 3.11+, microphone, speakers, internet, and an OpenAI API key.

```bash
git clone https://github.com/smakubi/axiomcart-ai-assistant.git
cd axiomcart-ai-assistant
git switch workshop/voice-cascade
cd workshop/local
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `OPENAI_API_KEY` to `.env`. On Windows, activate with `.venv\\Scripts\\activate`. Keep API keys private.

## Build it, one problem at a time

| # | Run | Discover | Production lesson |
|---|---|---|---|
| 1 · Record | `python voice.py record` | Why samples and WAV? | Capture, encoding, transport |
| 2 · STT | `python voice.py stt` | Why are IDs misheard? | Validation, vocabulary, evaluation |
| 3 · LLM | `python voice.py llm --text "Find shoes"` | Can a model know inventory? | Tools, grounding, context |
| 4 · TTS | `python voice.py tts` | Why do prices sound odd? | Text normalization, audio playback |
| 5 · Cascade | `python voice.py cascade` | Why does it feel slow? | First-audio latency, streaming |
| 6 · VAD | `python voice.py vad --silence-ms 200` | Why are pauses cut off? | Endpointing, noise, thresholds |
| 7 · Loop | `python voice.py loop` | Why can't we interrupt? | Duplex, cancellation, echo |
| 8 · Frameworks | [LiveKit vs Pipecat](08-livekit-pipecat.md) | Why use a framework? | Sessions, transports, processors |

**Try this:** For VAD, rerun with `--silence-ms 1200`. Which version cuts you off? Which feels slower?

## Read more only when needed

- [Instructor notes & production tradeoffs](README.md)
- [Local Python source](local/voice.py) · [Setup details](local/README.md)
- [Real AxiomCart STT/TTS](../src/speech_api.py) · [Browser audio](../public/assets/live-transcription.mjs)

**Scope:** The local implementation is a batch, half-duplex teaching demo. Streaming STT, live TTS playback, and barge-in are explained but not implemented locally. Microphone and API smoke tests remain to be done before class.
