import numpy as np
from voice import SilenceDetector, rms, save_wav
import wave


def test_rms():
    assert rms(np.zeros(10, dtype=np.int16)) == 0
    assert rms(np.full(10, 16384, dtype=np.int16)) == 0.5


def test_silence_commits_after_speech():
    d = SilenceDetector(threshold=0.02, silence_ms=90, max_ms=1000)
    assert not d.update(0.0)
    assert not d.update(0.1)
    assert not d.update(0.0)
    assert not d.update(0.0)
    assert d.update(0.0)


def test_no_speech_until_timeout():
    d = SilenceDetector(max_ms=90)
    assert not d.update(0)
    assert not d.update(0)
    assert d.update(0)


def test_wav_header(tmp_path):
    path = tmp_path / "a.wav"
    save_wav(path, np.zeros(160, dtype=np.int16))
    with wave.open(str(path)) as f:
        assert f.getframerate() == 16000
        assert f.getnchannels() == 1
        assert f.getnframes() == 160
