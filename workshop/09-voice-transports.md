# WebSocket and WebRTC — how does live audio travel?

> **Customer problem:** Our local microphone belongs to the laptop running Python. In a deployed website, the customer's microphone belongs to their browser. How do its audio samples reach our service while the customer is still speaking?

## Predict before choosing a transport

Draw the boundaries first:

```text
Customer device           Network             Voice service
microphone → audio chunks ───────────────────→ STT → LLM
speaker    ← audio chunks ←─────────────────── TTS ← reply
```

Ask: Which arrows need to carry data continuously? Where do we detect a turn ending? Who stops an old reply when the user interrupts?

A transport moves data across the network. STT interprets audio, TTS creates audio, and the application decides turn-taking. Choosing a transport does not replace those responsibilities.

## Start with what we already ran: HTTP

`record` creates a file locally. `stt` uploads that file after recording ends. `tts-stream` reads a streaming HTTP response and plays arriving PCM chunks. That last exercise proves progressive playback does not require a WebSocket or WebRTC connection.

The original `loop` command does not monitor the microphone during playback. The new `duplex` and `barge-in` commands add concurrent local capture/playback; the transport server below connects browser audio to the same controller.

## WebSocket — an ongoing two-way message connection

WebSocket lets a client and server exchange messages over an open connection without repeatedly polling. Messages can contain binary audio or structured events such as partial transcripts and cancellation requests.

**Why useful:** A Python service can send microphone chunks and receive recognition events during one session. Explicit messages make the flow easy to inspect and customize.

**What we must build:** Define audio format, message types, bounded buffers, playback timing, authentication, reconnect behavior, and which reply a chunk belongs to. The standard browser WebSocket API has no automatic backpressure; queues need limits. Ordinary WebSocket uses reliable ordered TCP delivery, so delayed data can hold up later messages.

**Predict:** If receiving is slower than sending, should audio accumulate forever? What happens if a cancellation message arrives after obsolete audio has already been queued?

**Exit question:** Does opening a WebSocket automatically make our sequential Python loop listen during playback? No; we must change its control flow too.

Reference: [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API).

## WebRTC — a real-time media connection

WebRTC provides live audio/video tracks and data channels. A peer can be a browser or a media service; it does not have to be another human's browser.

**Why useful:** Its media stack handles codecs, packet timing, jitter buffering, and adaptation to changing network conditions. These responsibilities matter when continuous conversation must remain usable despite variable packet arrival times. Browser audio capture can also offer echo cancellation, depending on device support and settings.

**What we must build:** A signaling exchange establishes the session. ICE finds a network path, STUN helps discover connectivity, and TURN can relay traffic when a direct path fails. The service still needs authentication, model connections, and conversation logic. Signaling may use HTTP or WebSocket; WebRTC does not prescribe the application's signaling protocol.

**Predict:** If WebRTC delivers user audio during a reply, who decides to cancel that reply? The application or agent runtime still owns that policy.

**Exit question:** Does WebRTC perform speech recognition or guarantee successful barge-in? No; media delivery alone supplies neither.

Reference: [MDN WebRTC API and guides](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API).

## Compare the responsibilities

| Question | Streaming HTTP in our CLI | WebSocket design | WebRTC design |
| --- | --- | --- | --- |
| What crosses the connection? | Request, then arriving TTS response bytes | Application-defined messages and audio chunks | Media tracks and optional data channels |
| Main teaching benefit | Understand progressive playback with little transport code | See audio and control events explicitly | Understand a media stack built for live communication |
| Where does our player run? | Local `sounddevice` speaker | Application supplies audio playback | Media stack delivers tracks for playback |
| Can the app listen and speak together? | Current CLI does not | Yes, with concurrent capture and playback | Yes, with concurrent capture and playback |
| Who decides to interrupt? | No spoken interruption in current CLI | Application/agent controller | Application/agent controller |

Neither transport is universally faster. Compare the same task, models, network conditions, and buffering policies before making a latency claim.

## Connect the vocabulary

- **Streaming:** process chunks before the complete result is available.
- **Full duplex:** input and output can operate simultaneously.
- **Barge-in:** recognize the user taking over, cancel the old reply, and preserve the new utterance.
- **WebSocket / WebRTC:** ways to transport data or media between devices/services.

These describe different aspects of the same system. A WebSocket connection can carry two-way traffic while an application chooses alternating turns. A WebRTC session can receive microphone audio while an application ignores interruptions.

## Five-minute teaching exercise

1. Replay `python voice.py tts-stream`. Identify the transport currently used: streaming HTTP.
2. Draw the microphone and speaker on the customer's laptop and STT/LLM/TTS on a remote service.
3. For WebSocket, label audio chunks, transcript events, cancel events, and reply IDs.
4. For WebRTC, label media tracks and the separate session setup/signaling exchange.
5. Ask: “Which part detects user speech? Which part cancels playback? Which part moves the bytes?”

Continue to the [framework comparison](08-livekit-pipecat.md) to see which responsibilities a framework coordinates.

## Run both transports

Follow the [live exercise guide](local/LIVE-EXERCISES.md). `python voice.py transport-server --offline` serves a local page where you can select WebSocket or WebRTC and compare the same Python turn controller. Restart without `--offline` for STT/LLM/TTS calls. This implementation is for same-computer teaching; it is not a remotely deployed service.
