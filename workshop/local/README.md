# Local Python voice workshop — Wednesday coaching

This is a **standalone learning companion** to the real AxiomCart code, not a replacement for its browser/WebRTC deployment. All microphone capture, control flow, and playback are Python. STT, LLM, and TTS inference use cloud APIs.

## Setup
Use Python 3.11+ with a working microphone and speakers. On macOS you may need `brew install portaudio`; on Linux install PortAudio development packages if pip cannot install sounddevice. Grant your terminal microphone permission.

```bash
cd workshop/local
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to set OPENAI_API_KEY; never commit your key
python voice.py --help
```

On Windows activate with `.venv\\Scripts\\activate`.

## Run in order — predict, run, observe, explain
| Step | Command | Question to ask before running |
| --- | --- | --- |
| 1. Record | `python voice.py record --seconds 5` | Why 16 kHz mono 16-bit WAV? |
| 2. STT | `python voice.py stt` | Why upload audio bytes instead of a string? |
| 3. LLM | `python voice.py llm --text "Show me running shoes"` | Why separate reasoning from transcription? |
| 4. TTS | `python voice.py tts --text "Welcome to AxiomCart"` | Why return audio rather than JSON text? |
| 5. Cascade | `python voice.py cascade` | Which stage makes us wait? |
| 6. Silence | `python voice.py vad --silence-ms 700` | What happens if the user pauses mid-sentence? |
| 7. Loop | `python voice.py loop` | Why is this turn-based, not full duplex? |
| 8. Streaming TTS | `python voice.py tts-stream --text "Welcome to AxiomCart"` | Can sound start before generation finishes? |

Run offline unit tests: `python -m pytest tests -q`.

## What to teach, slowly
1. A microphone produces a series of numeric samples. WAV is a container with format metadata. At 16 kHz, 16-bit, mono: 32 KB/s raw PCM.
2. Batch STT waits for a complete recording. Its output is text.
3. The LLM accepts text and returns text. Swapping it for AxiomCart's LangGraph changes the reasoning stage, not the voice boundaries.
4. TTS accepts text and produces sound samples, here packaged in a WAV file.
5. Sequential calls add latency. The initial `cascade` includes audio playback in its last timing; measure generation separately before claiming time-to-first-audio.
6. The silence detector measures energy, **not actual speech recognition**. Try --threshold 0.01 and 0.08; try --silence-ms 200 and 1200. Discuss noise and false cuts.
7. The loop is half-duplex: it does not listen while speaking. True barge-in requires simultaneous input monitoring and playback cancellation.

## Map back to real AxiomCart
- `voice.py:transcribe` ↔ `src/speech_api.py:/api/voice/transcribe`
- `voice.py:think` ↔ `src/graph.py` (the full application has routing and tools)
- `voice.py:speak` ↔ `src/speech_api.py:/api/voice/speak`
- `voice.py:SilenceDetector` ↔ `public/assets/live-transcription.mjs:TurnDetector`
- Local WAV files ↔ browser MediaStream/WebRTC transport

## Next exercise: streaming TTS, step by step

Already ran the cascade? From your repository root, update the workshop branch:

```bash
git switch workshop/voice-cascade
git pull --ff-only origin workshop/voice-cascade
cd workshop/local
source .venv/bin/activate
python voice.py --help
```

Keep your existing `.env`. No new dependencies, browser, or framework is needed.

1. **Predict:** `tts` downloads a full WAV before playback. When could a streaming player start? Does streaming shorten the spoken sentence?
2. **Run the baseline:** `python voice.py tts --text "Welcome to AxiomCart. Let me help you find a comfortable pair of shoes for your next long walk."`
3. **Run progressively:** `python voice.py tts-stream --text "Welcome to AxiomCart. Let me help you find a comfortable pair of shoes for your next long walk."`
4. **Observe:** Listen for playback beginning while audio is still arriving. Read **First audio submitted to speaker**, measured from just before the request to the first playable chunk submitted. Device startup and network wait are included; device/output latency is not. This is an estimate of first-audio latency, not a microphone measurement of audible onset. **TTS request + playback** ends after the speaker drains; it includes the spoken duration, not just generation. Results vary across calls.
5. **Explain:** The API sends headerless 24 kHz mono signed 16-bit little-endian PCM ([format reference](https://developers.openai.com/api/docs/guides/text-to-speech)). Each sample needs two bytes. The iterator asks for 960-byte chunks (20 ms), and the player carries a split sample into the next chunk. It writes complete samples immediately rather than saving `reply.wav`. Blocking speaker writes provide backpressure; application buffering is a chunk plus at most one leftover byte, not the whole utterance.
6. **Try cancellation:** Use a longer phrase and press Ctrl+C during playback. Queued audio is aborted, the device and HTTP response close, and the command returns. Retry to verify the device is available again. Empty audio or a final incomplete sample raises a clear error; API/device errors propagate after cleanup.
7. **Discuss the tradeoff:** Small chunks favor a quick start but network pauses can cause audible gaps. Speaker underflows are reported. A bounded producer/consumer jitter buffer is a future refinement. This streams audio output from a complete text prompt; STT and LLM output are still batch, and the loop remains half-duplex without barge-in.

If `tts-stream` is an invalid choice, verify `git branch --show-current` and `git log -1`, then repeat the pull above. If the device cannot open at 24 kHz, check `python -m sounddevice` and your default speaker settings. Never play this PCM at the microphone's 16 kHz rate: that changes speed and pitch. The voice is AI-generated.

## Safety / limitations
This is a learning demo: no user authentication, persistent conversation state, production VAD, automatic noise calibration, or retry policy. It records audio locally to `recording.wav` and batch generated speech to `reply.wav`; `tts-stream` plays without saving a file. Delete these after class if needed. The loop may time out in a silent room after 15 seconds. Use headphones to prevent speaker echo in more advanced full-duplex exercises.


## Instructor quality bar
The learning material in [the workshop index](../README.md) is the canonical sequence. Before each command, state the problem and ask students to predict the outcome. After running it, explain the mechanism and discuss the production tradeoff. Avoid unexplained copy/paste or treating successful API calls as understanding.

### Environment and verification
Offline verification for the streaming addition: 14 local Python tests and 10 repository JavaScript tests passed. The broader Python suite passed 30 tests with one existing health-model expectation mismatch (`GLM-4.7` versus configured `GLM-5.3-Flash`). **Physical speakers/microphone and live API playback have not been verified in this chat**. Before class, run `python -m pytest tests -q`, then every command in the exercise table using a valid API key. If an API/model configuration differs in your account, update the example and retest. Do not claim the production features are already implemented locally.

### Expected failure scenarios to demonstrate
- Record in background noise: amplitude detection may treat noise as speech.
- Say a product ID or price: transcription and pronunciation may be wrong.
- Speak with a long pause: a short silence threshold can cut off the utterance.
- Interrupt playback: the half-duplex loop ignores the user until playback ends.
- Remove the API key: network inference should fail clearly rather than silently.

### Success criteria
Students can draw the audio→text→text→audio boundaries, explain the timing of each stage, identify one concrete failure at every boundary, and describe one production mitigation without assuming a framework magically removes the problem.
