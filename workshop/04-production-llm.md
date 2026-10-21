# A transcript is not an answer

> **Customer problem:** The customer asks for a shoe under $100. STT can transcribe that sentence, but cannot search inventory. A plain LLM may confidently invent products.

## Predict before coding
Ask learners what the simplest implementation will do, and which part might fail. Give them a moment to answer before running anything.

## Run the smallest version
From `workshop/local`:

```bash
python voice.py llm --text "Recommend running shoes under $100"
```

## Experiment — change one thing
Ask the same question twice. Then ask about a nonexistent order. Identify any claims that require a catalog or order API.

## Why the system behaves this way
The LLM consumes text regardless of whether it came from STT or keyboard. It generates language, but without tools or grounding it does not know real-time inventory.

## What production teams do differently
Use retrieval/tools for factual business state, validate tool arguments, maintain conversation context, constrain risky actions, and treat transcript content as untrusted instructions. Keep answers concise for spoken delivery.

## Look at the real AxiomCart code
- [Python STT/TTS service](../../src/speech_api.py)
- [Transcription session configuration](../../src/voice.py)
- [Browser audio transport and turn lifecycle](../../public/assets/live-transcription.mjs)
- [Python local companion](local/voice.py)

## Check for understanding
**What additional component is needed before a voice agent can truthfully answer 'Where is my order?'** Have the learner answer in their own words and point to the relevant function in the code.

## Scope and honesty
This chapter uses the runnable local baseline. It does not imply that production-grade behavior described above is implemented in the local demo. The advanced capability is a design exercise unless a separate runnable implementation and test are provided.
