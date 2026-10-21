# Voice engineering, from first principles
### Wednesday coaching · AxiomCart workshop branch

> **Build the naive version. Observe the failure. Understand the constraint. Improve the design.**

This workshop is deliberately **not** a collection of pasted API calls. It is a guided engineering investigation into why real-time voice agents are hard. We use a small Python CLI for hands-on experiments and inspect the actual AxiomCart implementation when we reach browser/WebRTC boundaries. We replace LangGraph with one LLM call so orchestration complexity doesn't hide the voice concepts.

**Audience:** Python learners familiar with functions and HTTP APIs. **Environment:** laptop with microphone, speakers, Python 3.11+, internet, provider API key. **Expected result:** a runnable half-duplex cascade, measurable failure modes, and an informed understanding of how production systems differ.

## The system under study

```text
Human speech
    ↓  microphone, sampling, audio encoding
Audio input
    ↓  STT: audio → words
Transcript
    ↓  LLM: words → response
Answer
    ↓  TTS: words → waveform
Speaker output
```

The first version is sequential. That is intentional: it creates observable latency, poor turn-taking, and inability to interrupt. These limitations motivate real engineering decisions.

## Teaching method
Each chapter follows **the same rhythm**:

1. **The customer problem** — a concrete situation that fails or feels unnatural.
2. **Prediction** — ask learners what will happen before showing code.
3. **Minimal implementation** — the few lines that expose the mechanism.
4. **Experiment** — run it, change one variable, and compare.
5. **Engineering explanation** — why the result occurs; include the important tradeoff.
6. **Production practice** — what teams typically add, and what is deliberately missing here.
7. **Exit question** — require a verbal explanation, not a memorized definition.

Avoid claiming a threshold, model, sample rate, or transport is universally best. Distinguish latency *measurements* from invented targets.

## Learning path

| Chapter | Real problem | Run locally | Production connection |
| --- | --- | --- | --- |
| [01. Where audio begins](01-voice-boundary.md) | Browser cannot access server's microphone | `python voice.py record` | Device permission, audio transport, short-lived credentials |
| [02. When is a turn finished?](02-stt-turns.md) | Long pauses cut users off | `python voice.py vad` | VAD, endpointing, finalization, noise |
| [03. Transcription](03-production-stt.md) | Product names and IDs are misheard | `python voice.py stt` | Language hints, vocabulary, confidence/evaluation |
| [04. Reasoning](04-production-llm.md) | A transcript isn't a useful answer | `python voice.py llm` | Context, tools, prompt injection, grounding |
| [05. Speech synthesis](05-production-tts.md) | Response is text, not sound | `python voice.py tts` | Voices, chunking, PCM, output playback |
| [06. Latency](06-production-latency.md) | Assistant feels slow | `python voice.py cascade` | First-audio latency, instrumentation, streaming |
| [07. Conversation](07-production-conversation.md) | Assistant cannot be interrupted | `python voice.py loop` | Duplex, cancellation, echo, state machines |
| [08. Frameworks](08-livekit-pipecat.md) | Custom orchestration grows complex | Compare implementations | LiveKit, Pipecat, transport/processor tradeoffs |

All commands run from `workshop/local` after following [local setup](local/README.md). **The Python exercises implement batch inference and a local silence-based loop.** They do not yet implement true streaming STT, chunk-by-chunk audible TTS, or barge-in. Those are taught as production extensions, not mislabeled as completed functionality.

## How to facilitate
Have learners write down three columns: **observation**, **hypothesis**, **change**. Ask for a prediction before each experiment. Run the same test twice when comparing parameters. Pause after each section and have one learner explain the mechanism without using the library's name.

### Honest limitations
AxiomCart's production-facing web architecture uses JavaScript for browser microphone/WebRTC and Python for STT/TTS API configuration and agent reasoning. The local companion uses `sounddevice` instead; it is not a byte-for-byte reproduction of the browser transport. Cloud inference still requires network connectivity and credentials. Do not paste secrets into notebooks or commit `.env` files.

**Code references:** [real voice configuration](../../src/voice.py), [real speech API](../../src/speech_api.py), [real browser streaming adapter](../../public/assets/live-transcription.mjs).
