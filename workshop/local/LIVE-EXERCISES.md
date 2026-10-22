# Full duplex, barge-in, WebSocket, and WebRTC — runnable exercises

These extend the existing `voice.py` exercises. Use Python 3.11+ and headphones.
STT and LLM are still batch calls after a turn ends; TTS streams progressively.
The microphone now remains active while the assistant generates and plays a reply.

## 1. Update and install

From the repository root:

```bash
git switch workshop/voice-cascade
git pull --ff-only origin workshop/voice-cascade
cd workshop/local
source .venv/bin/activate
python -m pip install -r requirements-live.txt
python voice.py --help
```

Keep your existing `.env` and `OPENAI_API_KEY`. The new native Python commands use the base dependencies; the optional requirements file also installs the local server, WebRTC media library, and test dependencies. No Node.js build or framework account is needed. Windows: use `.venv\Scripts\activate`.

## 2. Prove capture and playback without API calls

```bash
python voice.py barge-in --offline
```

Speak a short sentence and pause. You should hear a quiet three-second tone. Speak again during the tone; it should stop. The next completed utterance starts another tone. Ctrl+C exits and releases the microphone/speaker.

This tests devices, detection, and cancellation; it does not transcribe or understand your words. Offline mode is also available for `duplex` and `transport-server`. Keep headphone volume comfortable.

## 3. Full duplex without interruption

**Predict:** Can we capture speech while the assistant continues talking?

```bash
python voice.py duplex --silence-ms 700
```

Ask: “Explain how to choose walking shoes.” While the assistant speaks, say “Actually, I need boots” and pause. It should keep speaking and print `queued_turn` when your new turn ends. It answers that captured turn after finishing the current reply.

**Explain:** Input and output operate concurrently. This mode deliberately does not cancel output. It keeps only the latest one pending turn, so several overlapping requests do not create an endless queue.

## 4. Add voice-triggered barge-in

**Predict:** What changes if user speech invalidates the current reply immediately?

```bash
python voice.py barge-in --silence-ms 700
```

Repeat the previous request and correction. After about 120 ms of sustained sound above the threshold, the controller stops queued playback and cancels the current async request. It retains the beginning of the correction, waits for your silence, then answers the correction. Detection/device buffering adds latency, so cancellation is not acoustically instantaneous.

**Explain these distinct timers:**

- `--threshold 0.025`: loudness needed to count as sound, not a probability of speech.
- Sound confirmation: 120 ms above threshold before taking the turn. A brief click should not interrupt.
- `--silence-ms 700`: quiet after detected sound before sending the user's completed turn to STT.
- Pre-roll: up to 200 ms of prior input retained so the sound-confirmation delay does not lose the start.
- Maximum captured turn: 15 seconds. Continuous noise may reach that limit.

Try `--silence-ms 200` versus `1200`. Lowering this setting changes endpointing, not how long speech must last to interrupt. To reduce background-triggered interruptions, try a higher `--threshold`; raising it too far misses quiet speech. These commands use a teaching energy detector, not production VAD.

## 5. Run the WebSocket transport

```bash
python voice.py transport-server --offline
```

Open **http://127.0.0.1:8765** in a current browser on the same computer. Select **WebSocket**, keep barge-in checked, click **Start microphone**, and allow microphone access. Speak, pause, listen for the tone, then interrupt it. Click **End session** before changing transports.

**Explain:** The browser sends 24 kHz mono int16 PCM in 20 ms binary frames. Python does turn detection and reply control. Output audio and status events return as WebSocket messages. The browser acknowledges played chunks, limiting output to five chunks (100 ms) in flight instead of accumulating unlimited audio. The microphone's send buffer is also capped; overload ends the session rather than silently corrupting a turn.

Unchecked barge-in gives full duplex with a queued next turn. The **Stop reply** button manually cancels output; distinguish that from voice-triggered interruption.

## 6. Switch to WebRTC

On the same page, select **WebRTC** and start again. Run the same tone/interruption comparison.

**Explain:** An HTTP offer/answer exchange establishes the peer connection. Audio travels as WebRTC media tracks; status/cancel events use a WebRTC data channel. The browser and `aiortc` handle media encoding/decoding, clocking, and delivery. Python resamples incoming audio for the same turn controller used by WebSocket and the native commands.

This is an actual local WebRTC media connection, not a WebSocket renamed “WebRTC.” It uses host ICE candidates without a STUN/TURN service. It demonstrates peers on the same computer, not a deployment across arbitrary networks. Browser or OS network permissions may be needed; failed negotiation should be checked rather than presented as a working demo.

## 7. Replace the offline tone with the shopping assistant

Stop the server with Ctrl+C and restart without `--offline`:

```bash
python voice.py transport-server
```

Reload the page and repeat both transports. Your server `.env` supplies the key; no API key is sent to the browser. Audio/text are sent to the configured OpenAI APIs. The browser uses a small amount of JavaScript for microphone/media access; all AI and turn-control logic remains Python. The original local CLI exercises remain Python-only.

## Teaching checklist

| Demonstration | Ask before running | What to observe |
| --- | --- | --- |
| `loop` baseline | Can it hear me while speaking? | Input and output alternate. |
| `duplex` | Does hearing me require stopping itself? | Captures a next turn, continues the current reply. |
| `barge-in` | What must stop when I take over? | Cancels requests, clears queued output, preserves correction. |
| WebSocket | Who defines audio chunks and control events? | Application framing, acknowledgments, bounded buffers. |
| WebRTC | Who handles live media delivery? | Media track + separate data channel; same interruption policy. |

For code walkthroughs: `live_core.py` owns capture and cancellation, `native_live.py` owns local audio callbacks, and `transport_server.py` adapts that engine to WebSocket/WebRTC. Each reply has an epoch; after interruption, late old-epoch audio cannot be enqueued again.

## Verification and limits

Run from `workshop/local` after installing `requirements-live.txt`:

```bash
python -m pytest tests -q
# Optional browser-audio logic tests if Node.js is installed:
node --test tests/js/*.test.mjs
```

The WebRTC integration test opens UDP sockets between real local test peers; restricted environments must allow that. Tests use synthetic microphone audio and the offline tone backend; they do not require a key. Browser tests verify resampling and clearing stale playback sources. Verification in this change: 29 local Python tests and 12 JavaScript tests passed, including real two-peer WebRTC negotiation, media, and interruption. The existing application suite passed 30 tests with one pre-existing health-model expectation mismatch (`GLM-4.7` versus configured `GLM-5.3-Flash`). Physical microphone/speaker and paid API checks remain separate manual steps above.

- Use headphones first. Native mode has no echo cancellation; loudspeaker output can interrupt itself. Browser echo cancellation is requested but is device/browser dependent.
- Already-submitted device/network audio can leave a short audible tail after cancellation. WebRTC receiver jitter buffers cannot be synchronously cleared from this Python application.
- Async cancellation closes local request contexts and rejects stale results; a provider may already have performed billable computation.
- Each turn is independent. No conversation memory is maintained, so the assistant is not told it finished a reply that you interrupted.
- Browser sessions expire after ten minutes. Lost input, unsupported devices, playback-ack timeouts, and connection failures require restarting the session.
- The server binds to `127.0.0.1`, accepts same-origin local sessions, and limits concurrent sessions. It is a local teaching server, without a deployment-ready authentication system or remote TURN configuration.
- If audio devices reject 24 kHz, run `python -m sounddevice` to inspect the defaults; select compatible OS input/output devices. If WebRTC fails, compare the independently selectable WebSocket exercise and inspect the local server output.
