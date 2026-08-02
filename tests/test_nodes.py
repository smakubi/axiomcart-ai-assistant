from src.nodes import fallback_routing_decision, plain_spoken_text


def test_fallback_router_handles_order_requests() -> None:
    decision = fallback_routing_decision("Where is order ORD102?")
    assert [task.agent for task in decision.tasks] == ["support_agent"]


def test_fallback_router_handles_mixed_requests() -> None:
    decision = fallback_routing_decision("Order ORD102 is late. Show me Sony alternatives too.")
    assert [task.agent for task in decision.tasks] == ["support_agent", "product_agent"]


def test_plain_spoken_text_removes_markdown_markers() -> None:
    assert plain_spoken_text("**Delayed**\n- Arrives Friday") == "Delayed\nArrives Friday"
