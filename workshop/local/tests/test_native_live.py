import numpy as np
from native_live import SpeakerBuffer


def test_reset_discards_stale_audio_and_callback_fills_silence():
    speaker = SpeakerBuffer()
    speaker.put(0, bytes([1, 0]) * 480)
    speaker.reset(1)
    speaker.put(0, bytes([2, 0]) * 480)
    out = np.ones((480, 1), dtype="int16")
    speaker.callback(out, 480, None, None)
    assert not out.any()
    speaker.put(1, bytes([3, 0]) * 480)
    speaker.callback(out, 480, None, None)
    assert (out == 3).all()
