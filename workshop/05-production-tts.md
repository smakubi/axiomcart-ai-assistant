# Text is not sound

> **Customer problem:** The LLM says 'Your order is ORD102 and costs $19.99.' A speech synthesizer may pronounce IDs, currency, or acronyms awkwardly.

## Predict before coding
Ask learners what the simplest implementation will do, and which part might fail. Give them a moment to answer before running anything.

## Run the smallest version
From `workshop/local`:

```bash
python voice.py tts --text "Your order ORD102 costs $19.99"
```

## Experiment — change one thing
Compare the generated pronunciation of order IDs, abbreviations, punctuation, and long paragraphs. Inspect reply.wav and listen.

## Why the system behaves this way
TTS maps text into a time-varying audio signal. WAV carries metadata and PCM samples; a browser or sound device must decode/play the signal at the correct sample rate.

## What production teams do differently
Normalize text for speech, chunk at sensible boundaries, use supported audio formats, avoid leaking sensitive content in logs, choose voices deliberately, and evaluate intelligibility and naturalness on real customer language.

## Look at the real AxiomCart code
- [Python STT/TTS service](../../src/speech_api.py)
- [Transcription session configuration](../../src/voice.py)
- [Browser audio transport and turn lifecycle](../../public/assets/live-transcription.mjs)
- [Python local companion](local/voice.py)

## Check for understanding
**Why is displaying the LLM answer faster than waiting to hear the complete answer?** Have the learner answer in their own words and point to the relevant function in the code.

## Scope and honesty
This chapter uses the runnable local baseline. It does not imply that production-grade behavior described above is implemented in the local demo. The advanced capability is a design exercise unless a separate runnable implementation and test are provided.
