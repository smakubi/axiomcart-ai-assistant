from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_home_serves_teaching_interface() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Multi-agent shopping" in response.text


def test_graph_metadata_is_key_free() -> None:
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert [node["id"] for node in response.json()["nodes"]] == [
        "orchestrator",
        "product_agent",
        "support_agent",
        "synthesizer",
    ]


def test_architecture_returns_source_backed_components() -> None:
    response = client.get("/api/architecture")
    assert response.status_code == 200
    components = {item["id"]: item for item in response.json()["components"]}
    assert "async def orchestrator" in components["orchestrator"]["source"]
    assert components["graph"]["path"] == "src/graph.py"
    assert "build_specialist_subgraph" in components["subgraphs"]["source"]
    assert "Command.PARENT" in components["subgraphs"]["source"]


def test_health_prefers_baseten(monkeypatch) -> None:
    monkeypatch.setenv("BASETEN_API_KEY", "test-baseten-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "baseten"
    assert payload["model"] == "thinkingmachines/inkling-small"
    assert payload["speech_configured"] is True
    assert payload["transcription_model"] == "gpt-4o-mini-transcribe"
    assert payload["speech_model"] == "gpt-4o-mini-tts"
    assert payload["speech_voice"] == "marin"


def test_speech_endpoint_streams_natural_voice(monkeypatch) -> None:
    calls = []

    class FakeSpeechResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def iter_bytes(self, chunk_size):
            assert chunk_size == 4_096
            yield b"first"
            yield b"second"

    class FakeStreamingSpeech:
        def create(self, **kwargs):
            calls.append(kwargs)
            return FakeSpeechResponse()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "test-openai-key"
            self.audio = type(
                "FakeAudio",
                (),
                {
                    "speech": type(
                        "FakeSpeech",
                        (),
                        {"with_streaming_response": FakeStreamingSpeech()},
                    )()
                },
            )()

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr("src.api.AsyncOpenAI", FakeAsyncOpenAI)

    response = client.post("/api/voice/speak", json={"text": "Welcome to AxiomCart."})

    assert response.status_code == 200
    assert response.content == b"firstsecond"
    assert response.headers["content-type"].startswith("audio/pcm")
    assert response.headers["x-speech-model"] == "gpt-4o-mini-tts"
    assert response.headers["x-speech-voice"] == "marin"
    assert response.headers["x-audio-sample-rate"] == "24000"
    assert calls[0]["stream_format"] == "audio"
    assert calls[0]["response_format"] == "pcm"
    assert "warm, natural" in calls[0]["instructions"]


def test_chat_requires_a_key_when_server_is_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/chat/stream",
        json={"message": "hello", "thread_id": "test-thread"},
    )
    assert response.status_code == 401
