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


def test_health_prefers_baseten(monkeypatch) -> None:
    monkeypatch.setenv("BASETEN_API_KEY", "test-baseten-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["provider"] == "baseten"
    assert response.json()["model"] == "thinkingmachines/inkling-small"
    assert response.json()["speech_configured"] is True


def test_chat_requires_a_key_when_server_is_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/chat/stream",
        json={"message": "hello", "thread_id": "test-thread"},
    )
    assert response.status_code == 401
