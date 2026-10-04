"""Speech configuration for the cascaded STT → graph → TTS demo."""

LIVE_TRANSCRIPTION_MODEL = "gpt-live-transcribe"


def transcription_session_config() -> dict:
    """Stream text only; the application commits turns and owns all reasoning/TTS."""
    return {
        "type": "transcription",
        "audio": {
            "input": {
                "transcription": {
                    "model": LIVE_TRANSCRIPTION_MODEL,
                    "languages": ["en"],
                    "delay": "low",
                    "prompt": "A shopping assistant discussing products and order IDs like ORD102.",
                },
                # Live transcription does not support server VAD. The browser
                # sends input_audio_buffer.commit after its local silence detector.
                "turn_detection": None,
                "noise_reduction": {"type": "near_field"},
            }
        },
    }
