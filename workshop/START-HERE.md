# Start here — Wednesday Voice Cascade Workshop

**Goal:** Build and understand a local Python voice assistant one boundary at a time: microphone → STT → LLM → TTS → speaker. Then deliberately break it and discover why production systems use VAD, streaming, cancellation, and voice frameworks.

**This is the student-facing runbook.** The [instructor guide](README.md) has the rationale and production discussion for each lesson. The [local reference](local/README.md) explains the implementation.

## Before class — set up once

Use Python 3.11+ on a laptop with a microphone, speakers, and internet. Cloud model calls incur provider charges.

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

On Windows, activate with `.venv\\Scripts\\activate` instead. Open `.env` and set `OPENAI_API_KEY`. Do not commit or share this file. On macOS, allow microphone access to Terminal; install PortAudio if `sounddevice` needs it. Run `python voice.py --help` to check setup.

## Exercise 1 — Can Python hear you?
Read [audio boundary](01-voice-boundary.md).

```bash
python voice.py record --seconds 5
```

Speak a sentence and check that `recording.wav` exists. **Predict:** why is 16 kHz mono 16-bit audio about 32 KB/s? **Observe:** the CLI waits for the entire five seconds. **Production:** a web app must capture audio in the browser and transport it; remote Python cannot read your laptop microphone.

## Exercise 2 — How does STT turn audio into words?
Read [STT challenge](03-production-stt.md).

```bash
python voice.py stt
```

Say a product name or order ID in the recording. **Predict:** will it be transcribed exactly? **Observe:** compare the output with what you said. **Production:** domain hints, entity validation, error analysis, and noisy-audio testing.

## Exercise 3 — What is the LLM responsible for?
Read [LLM challenge](04-production-llm.md).

```bash
python voice.py llm --text "Show me running shoes under 100 dollars"
```

**Predict:** can the LLM know AxiomCart's actual inventory? **Observe:** it may produce plausible but ungrounded product suggestions. **Production:** tool calls, retrieval, state, guardrails, and concise spoken responses.

## Exercise 4 — How does text become speech?
Read [TTS challenge](05-production-tts.md).

```bash
python voice.py tts --text "Order ORD102 costs 19 dollars and 99 cents"
```

Listen to the voice and inspect `reply.wav`. **Predict:** what could go wrong with prices, IDs, and acronyms? **Production:** text normalization, chunking, voice choice, playback buffers.

## Exercise 5 — Wire the complete cascade
Read [latency challenge](06-production-latency.md).

```bash
python voice.py cascade --seconds 5
```

Speak a request, then listen to the answer. Write down the measured STT and LLM durations. **Observe:** the TTS number includes playback, not just synthesis. **Production:** measure time-to-first-audio, not just total completion; overlap stages with streaming where safe.

## Exercise 6 — Who decides that you're done speaking?
Read [turn detection](02-stt-turns.md).

```bash
python voice.py vad --silence-ms 200
python voice.py vad --silence-ms 1200
```

Pause halfway through a sentence. **Predict:** which threshold cuts you off? **Observe:** different silence windows change responsiveness. **Production:** energy thresholds alone are fragile; use robust VAD, endpointing policies, and careful finalization.

## Exercise 7 — Make a repeated voice conversation
Read [conversation challenge](07-production-conversation.md).

```bash
python voice.py loop --silence-ms 700
```

Try to interrupt the assistant while it speaks. **Observe:** it does not listen during TTS playback. Press Ctrl+C to stop. **Production:** duplex audio, echo cancellation, concurrent tasks, cancellation and stale-buffer suppression.

## Exercise 8 — Why frameworks exist
Read [LiveKit and Pipecat comparison](08-livekit-pipecat.md). Compare our `cascade()` with Pipecat's processor pipeline and LiveKit's AgentSession. **Predict:** which pieces can the framework manage? **Production:** framework support does not automatically guarantee better latency; benchmark equivalent models, transports, and turn policies.

## Finish — explain the system without looking
1. Why do we need audio samples, STT, an LLM, and TTS as separate components?
2. What happens if silence is mistaken for the end of a sentence?
3. Which wait dominates the perceived latency?
4. Why can't this local loop handle interruptions?
5. What would LiveKit or Pipecat replace, and what would remain our responsibility?

## Known limitations
This is a local **half-duplex**, batch-inference teaching implementation. It requires API access and local audio hardware. Real-time streaming STT, progressive audible TTS, and barge-in are production design topics in these lessons, not completed features of `voice.py`. The code has not been smoke-tested on a real microphone and provider account in this chat; instructors should run the commands and `python -m pytest tests -q` before class.
