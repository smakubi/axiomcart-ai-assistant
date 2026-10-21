# Transcription is not understanding

> **Customer problem:** A customer says “ORD102” but STT writes “order one oh two.” The support lookup fails even though the audio sounds clear.

## Predict before coding
Ask learners what the simplest implementation will do, and which part might fail. Give them a moment to answer before running anything.

## Run the smallest version
From `workshop/local`:

```bash
python voice.py record --seconds 5
python voice.py stt
```

## Experiment — change one thing
Record a product name, a number, and an order ID. Compare the transcript with what was spoken. Repeat slowly and with background noise.

## Why the system behaves this way
An STT model predicts text from audio. It can produce plausible words that are wrong for the business domain. STT output is untrusted user input, not a validated order identifier.

## What production teams do differently
Use domain vocabulary/hints where supported, normalize and validate identifiers, evaluate with real noisy audio, monitor word error rate plus business-critical entity accuracy, and ask for confirmation before irreversible actions.

## Look at the real AxiomCart code
- [Python STT/TTS service](../../src/speech_api.py)
- [Transcription session configuration](../../src/voice.py)
- [Browser audio transport and turn lifecycle](../../public/assets/live-transcription.mjs)
- [Python local companion](local/voice.py)

## Check for understanding
**Why can a transcript look fluent yet be operationally wrong?** Have the learner answer in their own words and point to the relevant function in the code.

## Scope and honesty
This chapter uses the runnable local baseline. It does not imply that production-grade behavior described above is implemented in the local demo. The advanced capability is a design exercise unless a separate runnable implementation and test are provided.
