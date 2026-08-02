from src.nodes import (
    deterministic_routing_decision,
    fallback_routing_decision,
    format_order_result,
    format_product_results,
    plain_spoken_text,
)


def test_fallback_router_handles_order_requests() -> None:
    decision = fallback_routing_decision("Where is order ORD102?")
    assert [task.agent for task in decision.tasks] == ["support_agent"]


def test_fallback_router_handles_mixed_requests() -> None:
    decision = fallback_routing_decision("Order ORD102 is late. Show me Sony alternatives too.")
    assert [task.agent for task in decision.tasks] == ["support_agent", "product_agent"]


def test_deterministic_router_leaves_ambiguous_requests_to_the_model() -> None:
    assert deterministic_routing_decision("Can you help me choose?") is None


def test_product_results_use_usd() -> None:
    answer = format_product_results(
        {"products": [{"name": "Studio One", "price": 249.5, "rating": 4.8}]}
    )
    assert "$249.50" in answer


def test_order_results_are_ready_to_speak() -> None:
    answer = format_order_result(
        {
            "found": True,
            "order_id": "ORD102",
            "product": "QuietTone Headphones",
            "status": "Delayed",
            "estimated_delivery": "August 6",
            "delay_reason": "Weather",
        }
    )
    assert answer.startswith("Order ORD102")
    assert "weather" in answer


def test_plain_spoken_text_removes_markdown_markers() -> None:
    assert plain_spoken_text("**Delayed**\n- Arrives Friday") == "Delayed\nArrives Friday"
