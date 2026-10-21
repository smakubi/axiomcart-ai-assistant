# Real conversations are not alternating file uploads

> **Customer problem:** The assistant starts reading a long response. The customer interrupts: 'Actually, never mind.' Our loop keeps talking.

## Predict before coding
Ask learners what the simplest implementation will do, and which part might fail. Give them a moment to answer before running anything.

## Run the smallest version
From `workshop/local`:

```bash
python voice.py loop
```

## Experiment — change one thing
Speak while the assistant plays audio. Observe that it cannot hear you. Then try a long pause mid-utterance with --silence-ms 200 and 1200.

## Why the system behaves this way
The basic loop is half-duplex: it alternates recording and playback. Full-duplex requires simultaneous input monitoring and output, a state machine, and cancellation of stale audio and model work.

## What production teams do differently
Use VAD plus turn detection, echo suppression, barge-in policies, cancellable streaming tasks, conversation state, timeout/reconnection logic, and backpressure. Ensure cancelled audio chunks cannot play after a new turn.

## Look at the real AxiomCart code
- [Python STT/TTS service](../../src/speech_api.py)
- [Transcription session configuration](../../src/voice.py)
- [Browser audio transport and turn lifecycle](../../public/assets/live-transcription.mjs)
- [Python local companion](local/voice.py)

## Check for understanding
**What must keep running while TTS is speaking if interruptions are allowed?** Have the learner answer in their own words and point to the relevant function in the code.

## Scope and honesty
This chapter uses the runnable local baseline. It does not imply that production-grade behavior described above is implemented in the local demo. The advanced capability is a design exercise unless a separate runnable implementation and test are provided.
