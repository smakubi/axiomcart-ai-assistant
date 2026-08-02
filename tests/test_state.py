from src.state import merge_agent_results


def test_parallel_results_are_appended() -> None:
    product = {
        "agent": "product_agent",
        "label": "Product discovery",
        "answer": "A",
        "tool_names": ["search_product_catalog"],
    }
    support = {
        "agent": "support_agent",
        "label": "Order support",
        "answer": "B",
        "tool_names": ["get_order_status"],
    }
    assert merge_agent_results([product], [support]) == [product, support]


def test_empty_update_resets_previous_turn() -> None:
    previous = [
        {
            "agent": "product_agent",
            "label": "Product discovery",
            "answer": "A",
            "tool_names": [],
        }
    ]
    assert merge_agent_results(previous, []) == []
