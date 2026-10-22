"""Offline streaming contract tests: no API key or audio hardware required."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import voice


@pytest.fixture
def rig(monkeypatch):
    events, writes = [], []
    state = SimpleNamespace(chunks=[b'\x01', b'\x02\x03', b'\x04'], fail=None,
                            underflow=False, requests=[])

    @contextmanager
    def response(**kwargs):
        state.requests.append(kwargs)
        events.append('response-open')
        try:
            yield SimpleNamespace(iter_bytes=chunks)
        finally:
            events.append('response-close')

    def chunks(chunk_size):
        assert chunk_size == 960  # 20 ms of 24 kHz mono int16
        for chunk in state.chunks:
            events.append('receive')
            yield chunk
        if state.fail:
            raise state.fail
        events.append('eof')

    class Speaker:
        def __init__(self, **kwargs):
            assert kwargs == dict(samplerate=24000, channels=1, dtype='int16')
        def __enter__(self):
            events.append('speaker-open')
            return self
        def write(self, audio):
            events.append('write')
            writes.append(bytes(audio))
            return state.underflow
        def abort(self):
            events.append("abort-called")
        def __exit__(self, kind, value, tb):
            events.append('abort' if kind else 'drain')
            events.append('speaker-close')

    monkeypatch.setattr(voice.sd, 'RawOutputStream', Speaker)
    ticks = iter([10.0, 10.25, 11.5])
    monkeypatch.setattr(voice.time, 'perf_counter', lambda: next(ticks))
    state.client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(
        with_streaming_response=SimpleNamespace(create=response))))
    state.events, state.writes = events, writes
    return state


def test_plays_before_eof_and_preserves_split_samples(rig, capsys):
    voice.speak_stream(rig.client, 'Hello')
    assert rig.writes == [b'\x01\x02', b'\x03\x04']
    assert rig.events.index('write') < rig.events.index('eof')
    assert rig.events[-3:] == ['drain', 'speaker-close', 'response-close']
    assert rig.requests[0]['response_format'] == 'pcm'
    assert rig.requests[0]['input'] == 'Hello'
    output = capsys.readouterr().out
    assert '250 ms' in output and '1500 ms' in output


@pytest.mark.parametrize('chunks, message', [([], 'No audio'), ([b'x'], 'incomplete')])
def test_rejects_empty_or_truncated_pcm(rig, chunks, message):
    rig.chunks = chunks
    with pytest.raises(RuntimeError, match=message):
        voice.speak_stream(rig.client, 'Hello')
    assert rig.events[-1] == 'response-close'
    assert 'abort-called' in rig.events


@pytest.mark.parametrize('failure', [RuntimeError('network lost'), KeyboardInterrupt()])
def test_failure_and_cancel_close_both_streams(rig, failure):
    rig.fail = failure
    with pytest.raises(type(failure)):
        voice.speak_stream(rig.client, 'Hello')
    assert rig.events[-4:] == ['abort-called', 'abort', 'speaker-close', 'response-close']


def test_empty_chunks_ignored_and_underflows_reported(rig, capsys):
    rig.chunks = [b'', b'\x01\x02', b'']
    rig.underflow = True
    voice.speak_stream(rig.client, 'Hello')
    assert rig.writes == [b'\x01\x02']
    assert 'underflow' in capsys.readouterr().out


def test_cli_dispatch(rig, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test')
    monkeypatch.setattr(voice, 'OpenAI', lambda: rig.client)
    monkeypatch.setattr('sys.argv', ['voice.py', 'tts-stream', '--text', 'Test phrase'])
    voice.main()
    assert rig.requests[0]['input'] == 'Test phrase'


def test_speaker_write_failure_closes_streams(rig, monkeypatch):
    class BrokenSpeaker:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def write(self, audio):
            raise OSError('speaker disconnected')
        def abort(self):
            rig.events.append('abort-called')
        def __exit__(self, *args):
            rig.events.append('speaker-close')
    monkeypatch.setattr(voice.sd, 'RawOutputStream', BrokenSpeaker)
    with pytest.raises(OSError, match='speaker disconnected'):
        voice.speak_stream(rig.client, 'Hello')
    assert rig.events[-3:] == ['abort-called', 'speaker-close', 'response-close']


def test_model_and_voice_configuration(rig, monkeypatch):
    monkeypatch.setenv('VOICE_TTS_MODEL', 'tts-1')
    monkeypatch.setenv('VOICE_TTS_VOICE', 'alloy')
    voice.speak_stream(rig.client, 'Hello')
    assert rig.requests[0]['model'] == 'tts-1'
    assert rig.requests[0]['voice'] == 'alloy'


def test_cli_cancellation_is_clean(rig, monkeypatch, capsys):
    rig.fail = KeyboardInterrupt()
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test')
    monkeypatch.setattr(voice, 'OpenAI', lambda: rig.client)
    monkeypatch.setattr('sys.argv', ['voice.py', 'tts-stream'])
    voice.main()
    assert 'Stopped.' in capsys.readouterr().out
    assert rig.events[-1] == 'response-close'
