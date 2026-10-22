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

## Full duplex — can input and output run at the same time?

**Problem:** A customer starts correcting the request while the assistant is speaking. If the microphone is closed, that correction is lost.

| Concept | Meaning | Does it automatically stop the assistant? |
| --- | --- | --- |
| Half duplex | The application takes turns recording and playing audio. | No; it is not monitoring input during playback. |
| Full duplex | Microphone input and speaker output can run simultaneously. | No; the application still needs an interruption policy. |
| Interruption / barge-in | The application accepts user speech during a reply and stops that reply so the user can take the turn. | Yes, when the detected speech meets the configured policy. |

Full duplex is an input/output capability. Barge-in is behavior built on top of concurrent input monitoring and output. A full-duplex system can hear the user and deliberately continue speaking, for example when ignoring a short background sound. Streaming TTS only means playing arriving chunks; it does not establish full duplex or implement barge-in.

**Predict:** If we leave the microphone open during playback but never cancel playback, what will happen when the user speaks?

**Design exercise:** Sketch two concurrent paths:

```text
Microphone → input frames → speech/turn detection → user utterance
Speaker    ← audio buffer ← TTS chunks            ← assistant reply
```

The input path keeps running while the output path plays. The device must support simultaneous capture and playback. Opening both paths does not, by itself, decide whose turn it is.

**Exit question:** Can an assistant be full duplex and still fail to stop when interrupted? Why?

## Interruption / barge-in — what should happen when the user takes over?

**Problem:** The assistant says “Here are five walking shoes…” and the customer says “Actually, I need boots.” Continuing the old answer is unhelpful even if the microphone captured the correction.

**Predict:** Is detecting silence enough to stop the old answer promptly? No: silence helps decide when the user's turn ends. Barge-in usually starts from evidence that the user has begun speaking, according to an interruption policy.

Walk through the desired sequence:

1. Keep capturing input while the assistant speaks; retain the beginning of the user's utterance in a bounded pre-roll buffer.
2. Detect likely user speech. Apply the policy: a cough or speaker echo should not automatically cancel a reply.
3. Stop playback and discard queued audio for the old reply promptly.
4. Cancel old TTS/model work where supported. Mark the old reply obsolete so late chunks cannot restart playback; cancellation may not stop all remote computation immediately.
5. Continue capturing the correction until the user's turn ends, then transcribe it and generate the new reply.
6. Update conversation history to distinguish what was generated from what was actually played. Do not assume the user heard the entire interrupted answer.

A reply ID or generation counter lets the player reject chunks belonging to a cancelled reply. A shared cancellation signal alone is insufficient if stale chunks are already queued or arrive late.

**Runnable observation, not a barge-in implementation:**

```bash
python voice.py loop --silence-ms 700
```

Ask for a long explanation, then say “Actually, I need boots” during playback. The current loop does not monitor input at that time, so it does not capture the correction. Repeat the correction once listening resumes. Lowering `--silence-ms` changes the end of a recorded turn; it does not enable interruption during playback. Ctrl+C stops the program; that is manual cancellation, not voice-triggered barge-in.

**Headphone-first design exercise:** Explain how you would add an input task, a playback task, and a controller that invalidates old replies. Headphones reduce the assistant audio reaching the microphone. For speakerphone use, acoustic echo cancellation helps distinguish speaker output from user speech; a loudness threshold alone can mistake the assistant's voice for an interruption. Echo cancellation and noise suppression solve different problems.

**Exit question:** After playback stops, what prevents an old TTS chunk from playing again? What preserves the first words of the user's correction?

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
