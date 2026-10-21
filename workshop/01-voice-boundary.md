# Exercise 1 — Where does speech enter the system?

**Learning goal:** explain the path from a physical microphone to an STT service without treating the browser and Python server as the same computer.

## Begin with a question
A student opens AxiomCart on their laptop. The Python API runs on a server. **Which machine can hear the student's microphone? Why?**

Pause for answers. The browser can request microphone permission on the student's device. The remote Python server cannot simply call a local sound-card library to hear it.

## Mental model
Microphone → browser MediaStream → WebRTC audio track → transcription service → text events → browser → AxiomCart Python graph.

The microphone adapter is JavaScript because browser media APIs are exposed there. Most business logic remains Python.

## Look at the actual code
- `public/assets/live-transcription.mjs`: `getUserMedia` stream is passed into `LiveTranscription.connect(stream)`; `RTCPeerConnection` sends its audio track.
- `src/speech_api.py`: `POST /api/voice/session` creates a short-lived credential.
- `src/voice.py`: Python constructs the transcription-only session configuration.

### Predict before running
What would happen if we tried to put a permanent provider API key in the browser? Why mint a short-lived credential instead?

### Run and observe
1. Start the AxiomCart app (instructions in workshop README).
2. Allow microphone access.
3. Inspect the browser's network panel for the session request and WebRTC negotiation.
4. Say one short sentence and note when the transcript first appears.

### Teach the numbers
At 16,000 samples/second, mono, 16-bit PCM: 16,000 × 1 × 2 = 32,000 bytes per second, before transport overhead. This is an explanatory PCM example, **not** a claim that WebRTC transports uncompressed 16 kHz PCM.

### Check understanding
1. Where are microphone permissions granted?
2. Why does the browser need a transport to the transcription service?
3. What is the difference between an audio sample and a transcript?
4. Which parts of this architecture are written in Python?

**Exit criterion:** learner can draw the audio path and identify the browser/Python boundary without looking at the diagram.
