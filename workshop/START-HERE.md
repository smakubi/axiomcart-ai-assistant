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
| 8 · Streaming TTS | `python voice.py tts-stream` | Can playback start before the full reply arrives? | PCM framing, buffering, cancellation |
| 9 · Frameworks | [LiveKit vs Pipecat](08-livekit-pipecat.md) | Why use a framework? | Sessions, transports, processors |

**Try this:** For VAD, rerun with `--silence-ms 1200`. Which version cuts you off? Which feels slower?

## Read more only when needed

- [Instructor notes & production tradeoffs](README.md)
- [Local Python source](local/voice.py) · [Setup details](local/README.md)
- [Real AxiomCart STT/TTS](../src/speech_api.py) · [Browser audio](../public/assets/live-transcription.mjs)

**Next after the cascade:** Follow the [streaming TTS exercise](local/README.md#next-exercise-streaming-tts-step-by-step) to compare first-audio latency with total playback time.

**Scope:** The local implementation includes batch exercises, progressive PCM TTS playback, and a half-duplex loop. The original loop remains half duplex; the new [live exercises](local/LIVE-EXERCISES.md) add concurrent input/output, barge-in, and WebSocket/WebRTC transports. Streaming STT remains a future extension. Microphone and API smoke tests remain to be done before class.

## After the runnable loop: two separate design lessons

- [Full duplex](07-production-conversation.md#full-duplex--can-input-and-output-run-at-the-same-time): keep microphone input and speaker output active simultaneously.
- [Interruption / barge-in](07-production-conversation.md#interruption--barge-in--what-should-happen-when-the-user-takes-over): detect the user taking over, stop the old reply, discard stale audio, and capture the correction.

The concepts are implemented in the [runnable live exercises](local/LIVE-EXERCISES.md): `duplex`, `barge-in`, and `transport-server`. The original loop stays half duplex for comparison.

## How audio travels between devices

Read [WebSocket and WebRTC](09-voice-transports.md) after the full-duplex and interruption sections. Compare streaming HTTP, two-way messages, and real-time media; distinguish transport from STT/TTS and turn-taking. Then run `python voice.py transport-server --offline` to compare both transports using the [live exercise instructions](local/LIVE-EXERCISES.md).
