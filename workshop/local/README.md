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

## Streaming and interruptions: conceptual next step
AxiomCart already demonstrates WebRTC streaming STT and PCM TTS. The local Python CLI intentionally does not claim to implement streaming STT, progressive PCM playback, or barge-in. For a genuine streaming lesson, add an async producer/consumer architecture and measure time-to-first-audio. Never mistake downloading a complete WAV via a streaming HTTP response for real-time playback.

## Safety / limitations
This is a learning demo: no user authentication, persistent conversation state, production VAD, automatic noise calibration, or retry policy. It records audio locally to `recording.wav` and generated speech to `reply.wav`. Delete these after class if needed. The loop may time out in a silent room after 15 seconds. Use headphones to prevent speaker echo in more advanced full-duplex exercises.


## Instructor quality bar
The learning material in [the workshop index](../README.md) is the canonical sequence. Before each command, state the problem and ask students to predict the outcome. After running it, explain the mechanism and discuss the production tradeoff. Avoid unexplained copy/paste or treating successful API calls as understanding.

### Environment and verification
The code has been committed but **has not been run against a physical microphone or live API in this chat**. Before class, run `python -m pytest tests -q`, then every command in the exercise table using a valid API key. If an API/model configuration differs in your account, update the example and retest. Do not claim the production features are already implemented locally.

### Expected failure scenarios to demonstrate
- Record in background noise: amplitude detection may treat noise as speech.
- Say a product ID or price: transcription and pronunciation may be wrong.
- Speak with a long pause: a short silence threshold can cut off the utterance.
- Interrupt playback: the half-duplex loop ignores the user until playback ends.
- Remove the API key: network inference should fail clearly rather than silently.

### Success criteria
Students can draw the audio→text→text→audio boundaries, explain the timing of each stage, identify one concrete failure at every boundary, and describe one production mitigation without assuming a framework magically removes the problem.
