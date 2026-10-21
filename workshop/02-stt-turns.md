# Exercise 2 — How does the system know a question is finished?

**Learning goal:** distinguish speech detection, audio commit, partial transcripts, and finalized text.

## The problem
A customer says: “Show me ... [pause] ... running shoes under $100.” Should the shopping agent execute after “Show me”? Why not?

## Read the real code
- `src/voice.py`: `transcription_session_config()` requests a transcription-only session and sets `turn_detection` to `None`.
- `public/assets/live-transcription.mjs`: `TurnDetector` tracks amplitude and elapsed silence; `LiveTranscription.monitor()` commits the audio buffer; `TranscriptTurn` associates final text with the committed item.
- `src/speech_api.py`: `/api/voice/transcribe` is a separate recorded-audio fallback, using `gpt-4o-mini-transcribe`.

## Python model of the turn detector
This deliberately models the *logic* of AxiomCart's browser detector, not the microphone/WebRTC transport.

```python
class TurnDetector:
    def __init__(self, threshold=0.025, silence_ms=500):
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.started_at = None
        self.last_speech_at = None

    def update(self, volume, now_ms):
        if volume > self.threshold:
            if self.started_at is None:
                self.started_at = now_ms
            self.last_speech_at = now_ms
        return (
            self.last_speech_at is not None
            and now_ms - self.last_speech_at >= self.silence_ms
        )

detector = TurnDetector()
for time_ms, volume in [(0, .0), (100, .05), (300, .04), (600, .0), (850, .0)]:
    print(time_ms, detector.update(volume, time_ms))
```

**Predict:** At what timestamp will the detector return true? (850 ms: last above-threshold audio at 300 ms, then 550 ms elapsed.) Why would a 200 ms silence threshold risk cutting the customer off?

## Critical distinctions
- Amplitude threshold ≠ robust voice activity detection. Noise can cross the threshold.
- A partial transcript is for preview, not for invoking the shopping graph.
- A local end-of-turn decision triggers `input_audio_buffer.commit`; the app waits for the matching completed transcription event.
- Committing does not itself mean the transcription is finalized.
- A production implementation also needs max-turn limits, error handling, timeouts, and interruption policy.

## Observe the real application
Speak a sentence with a long pause in the middle. Repeat with a short pause. Compare the results and discuss why tuning the silence threshold trades responsiveness against premature turn endings.

## Check understanding
1. Why can we receive text before the user finishes speaking?
2. What does `input_audio_buffer.commit` mean?
3. Why shouldn't each transcription delta trigger LangGraph?
4. What can go wrong if background noise is loud?

**Exit criterion:** learner can explain the sequence: speech → silence → commit → final transcript → agent.
