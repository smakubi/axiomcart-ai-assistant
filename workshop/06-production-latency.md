# A correct answer can still feel broken

> **Customer problem:** The assistant waits through a five-second recording, STT, LLM, TTS generation, and playback. A user interprets the silence as failure.

## Predict before coding
Ask learners what the simplest implementation will do, and which part might fail. Give them a moment to answer before running anything.

## Run the smallest version
From `workshop/local`:

```bash
python voice.py cascade
```

## Experiment — change one thing
Write down measured STT and LLM times. Note that the current TTS number includes playback. Estimate the user-perceived wait separately; repeat with a shorter recording.

## Why the system behaves this way
Sequential stage times add. Streaming can overlap some work, but not all dependencies disappear. A first token is not a first audible phoneme, and time-to-complete is not time-to-first-audio.

## What production teams do differently
Instrument speech end, final transcript, LLM first token, TTS first audio byte, and first audible sample. Monitor p50/p95, distinguish network vs model vs buffering, and benchmark with realistic turns.

## Look at the real AxiomCart code
- [Python STT/TTS service](../../src/speech_api.py)
- [Transcription session configuration](../../src/voice.py)
- [Browser audio transport and turn lifecycle](../../public/assets/live-transcription.mjs)
- [Python local companion](local/voice.py)

## Check for understanding
**Which measurement would best explain why a customer thinks the agent is slow?** Have the learner answer in their own words and point to the relevant function in the code.

## Scope and honesty
This chapter uses the runnable local baseline. It does not imply that production-grade behavior described above is implemented in the local demo. The advanced capability is a design exercise unless a separate runnable implementation and test are provided.
