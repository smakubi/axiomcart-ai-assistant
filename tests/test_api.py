from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_home_serves_teaching_interface() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Watch a multi-agent system" in response.text


def test_graph_metadata_is_key_free() -> None:
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert [node["id"] for node in response.json()["nodes"]] == [
        "orchestrator",
        "product_agent",
        "support_agent",
        "synthesizer",
    ]


def test_chat_requires_a_key_when_server_is_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/api/chat/stream",
        json={"message": "hello", "thread_id": "test-thread"},
    )
    assert response.status_code == 401
