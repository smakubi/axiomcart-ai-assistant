from src.config import AgentContext, chat_model, server_model_config


def test_baseten_default_and_wire_thinking_control(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "test-key")
    monkeypatch.delenv("BASETEN_MODEL", raising=False)
    config = server_model_config()
    assert config.model_name == "zai-org/GLM-5.3-Flash"
    model = chat_model(AgentContext(api_key="test-key"))
    payload = model._get_request_payload("Hello")
    assert payload["reasoning_effort"] == "low"
    assert "extra_body" not in payload
    assert payload["max_completion_tokens"] == 1_500
    assert model.request_timeout == 15
    assert model.max_retries == 1


def test_custom_provider_model_does_not_receive_glm_specific_options():
    model = chat_model(AgentContext(api_key="test-key", model_name="custom/model"))
    payload = model._get_request_payload("Hello")
    assert "extra_body" not in payload
