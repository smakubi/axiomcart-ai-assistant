# Streaming a cascaded voice assistant

AxiomCart preserves three independently replaceable stages:

```text
Microphone ── WebRTC ── streaming STT ── final text ── LangGraph/Baseten
                                                      │
                                speaker ← PCM ← streaming TTS ← answer.ready
```

The transcription session cannot answer shopping questions or speak. It only
produces text. The graph remains responsible for routing, tools, specialist
subgraphs, checkpointing, and the final answer. TTS is a separate request.

## Trace one turn

1. The user starts voice. The browser requests `/api/voice/session`.
2. FastAPI uses the existing `OPENAI_API_KEY` to create a transcription-only
   short-lived credential. It returns only that credential and its expiration.
3. The browser adds the microphone track to a WebRTC peer connection and sends
   its SDP offer to OpenAI using the ephemeral credential. Microphone audio
   streams continuously while listening; no completed recording is uploaded.
4. Transcript deltas update a preview. A local RMS detector waits for 500 ms
   without speech, mutes the outgoing microphone track, and sends
   `input_audio_buffer.commit`. A 30-second speech limit also commits a turn.
5. The commit acknowledgement supplies an `item_id`. Only the matching final
   transcription event can call `sendMessage`; partial, stale, and duplicate
   events must not invoke tools. No final transcript within 15 seconds ends the
   session with a visible error.
6. The graph routes and runs its specialists. Missing order IDs still pause
   with `interrupt()`; the next finalized turn uses `Command(resume=...)`.
7. The synthesizer emits `answer.ready` with the assembled answer. The browser
   starts `/api/voice/speak` immediately, without waiting for the API's final
   checkpoint read. `run.completed` updates the transcript without speaking
   the answer twice.
8. TTS streams PCM16 at 24 kHz. Playback starts after 120 ms of audio is buffered
   and continues while additional bytes arrive. Listening resumes after playback.

There is no native speech-to-speech reasoning and no speculative execution on
partial transcripts. Specialist answers are currently assembled before speech;
this change does not token-stream specialist model output. The microphone is
muted during reasoning/playback, so this demo has sequential conversational
turns rather than barge-in. Ending/resetting closes the peer connection and
microphone and discards pending events.

## Example code: transcription-only session

The source-backed **Cascaded voice** card on `/architecture` displays the actual
configuration in `src/voice.py`. Its essential boundary is:

```python
session = {
    "type": "transcription",
    "audio": {
        "input": {
            "transcription": {
                "model": "gpt-live-transcribe",
                "languages": ["en"],
                "delay": "low",
            },
            "turn_detection": None,
        }
    },
}
secret = await client.realtime.client_secrets.create(
    session=session,
    expires_after={"anchor": "created_at", "seconds": 60},
)
```

The current live transcription model requires application-controlled commits;
it does not support server VAD. The browser's `TurnDetector` in
`public/assets/live-transcription.mjs` implements that boundary. WebRTC carries
audio, while the data channel carries transcript and commit events.

## Example code: send final text, never partial text

```javascript
// See TranscriptTurn for item matching and duplicate/cancellation guards.
const text = turn.handle(event);
if (event.type === 'conversation.item.input_audio_transcription.delta') {
  showCaption(turn.preview); // display only
}
if (text !== null) {
  sendMessage(text, { voiceInput: true }); // ordinary text graph request
}
```

`showCaption` is illustrative; the deployed browser uses the `onPreview`
callback. Run `node --test tests/js/*.test.mjs` to demonstrate short-pause,
commit, cancellation, and duplicate-event behavior without microphone access.

## Compare streaming versus recorded input

In Settings, choose **Streaming transcription** or **Recorded turn upload**.
Both use the same text graph and separate TTS endpoint. Recorded mode keeps
`MediaRecorder`, an 850 ms silence wait, and `/api/voice/transcribe` using
`gpt-4o-mini-transcribe`. It remains useful as a teaching comparison and when
WebRTC is unavailable; it is selected explicitly, not silently retried.

Speak the same prompts five times in each mode:

- “Show me wireless headphones under three hundred dollars.”
- “Where is order ORD102?”
- “Order ORD102 is late. Show me Sony alternatives too.”
- “I need help with an order.” Then supply “ORD102.”

Use the same microphone and network. Separate the first connection/cold start
from warm turns; compare medians and slowest turns rather than one result.
Check captions for order ID accuracy before attributing a delay to the graph.

## Read the timings correctly

| Visible metric | Streaming input definition |
| --- | --- |
| Listen | Last detected speech → commit; approximately 500 ms |
| Transcribe | Commit → matching final text received by browser |
| Reason | Server graph start → completion, including checkpoint bookkeeping |
| Speak | TTS request → estimated first scheduled audio playback |
| End of speech → first audio | Last detected speech → estimated first scheduled playback |

Playback timing is estimated from the Web Audio clock, not measured acoustically.
The graph may still finish bookkeeping while speech starts, so these stages
can overlap; their sum need not equal the end-to-end metric. In recorded mode,
Listen includes the recorded speech duration and Transcribe includes upload and
transcription. Recorded mode also reports end-of-speech-to-first-audio.

Before claiming a speed improvement, measure actual voice turns on the deployed
app. Key-free unit tests verify behavior, not provider latency or microphone
quality. Try a short mid-sentence pause, silence only, end/reset during a turn,
voice replies off, and a network disconnect.

## Deployment and provider boundaries

Keep `OPENAI_API_KEY` on the existing deployment. `BASETEN_API_KEY` still selects
Inkling reasoning; the new session endpoint uses the speech key independently.
A learner key in Settings continues to override reasoning and speech as before.
The ephemeral credential expires for connection establishment after 60 seconds;
it is held in memory, not localStorage. Session close releases browser resources.

Use `api/voice/session.py` as the Vercel entrypoint. Vercel handles the short
credential request; the audio connection is direct browser-to-provider WebRTC,
so a long-lived WebSocket server is not required.

References: [live transcription](https://developers.openai.com/api/docs/guides/realtime-transcription)
and [browser WebRTC connections](https://developers.openai.com/api/docs/guides/voice-webrtc?api=realtime).
