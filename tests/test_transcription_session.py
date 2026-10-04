from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.speech_api import app

client = TestClient(app)


def test_transcription_session_requires_speech_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/api/voice/session")
    assert response.status_code == 401


def test_session_returns_only_short_lived_transcription_credential(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.realtime = SimpleNamespace(client_secrets=SimpleNamespace(create=self.create))

        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(value="ephemeral-test", expires_at=1234)

        async def close(self):
            pass

    monkeypatch.setenv("OPENAI_API_KEY", "server-secret-never-returned")
    monkeypatch.setattr("src.speech_api.AsyncOpenAI", FakeClient)
    response = client.post("/api/voice/session")
    assert response.status_code == 200
    assert response.json() == {"value": "ephemeral-test", "expires_at": 1234}
    assert "server-secret" not in response.text
    assert response.headers["cache-control"] == "no-store"
    session = calls[0]["session"]
    assert session["type"] == "transcription"
    assert session["audio"]["input"]["turn_detection"] is None
    assert session["audio"]["input"]["transcription"]["model"] == "gpt-live-transcribe"


def test_provider_error_does_not_expose_credentials(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            self.realtime = SimpleNamespace(client_secrets=SimpleNamespace(create=self.create))

        async def create(self, **kwargs):
            raise RuntimeError("server-secret-never-returned")

        async def close(self):
            pass

    monkeypatch.setenv("OPENAI_API_KEY", "server-secret-never-returned")
    monkeypatch.setattr("src.speech_api.AsyncOpenAI", FakeClient)
    response = client.post("/api/voice/session")
    assert response.status_code == 502
    assert "server-secret" not in response.text
