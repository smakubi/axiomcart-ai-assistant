# Wednesday Voice Cascade Coaching

This workshop teaches the real AxiomCart voice stack from first principles. Work in order; each lesson introduces one problem, the smallest solution, an observable limitation, and a reason for the next improvement.

## Teaching contract
- Explain in simple English, slowly. One new idea at a time.
- First ask learners to predict what will happen. Then run the code, observe, and explain why.
- Use analogies only when they clarify the underlying mechanism.
- Keep the real AxiomCart source visible; avoid replacing it with an unrelated demo.
- Python is the primary teaching language. Treat browser JavaScript as a supplied microphone/WebRTC adapter; explain its role without requiring students to write it.
- Distinguish an amplitude threshold from actual speech-aware VAD.
- Distinguish provisional transcription deltas from final committed user turns.
- Measure latency, not just whether the demo works.

## Route through the code
1. [01 — The voice boundary](01-voice-boundary.md): why browser microphone capture differs from server-side Python; trace audio to STT.
2. [02 — STT and turn detection](02-stt-turns.md): inspect Python session config and browser commit lifecycle.
3. Next: finalized transcript → LangGraph → TTS → playback; streaming and interruptions.

## Run the real app
From the repository root, install dependencies with `uv sync`, configure the required API keys, then run `uv run uvicorn src.api:app --reload`. Open http://localhost:8000 and allow microphone access. Verify credentials and current model configuration before class; README model names may lag behind code.

Production app files are intentionally unchanged in this branch. The workshop adds teaching materials alongside them.
