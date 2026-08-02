from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.config import AgentContext
from src.graph import build_graph
from src.subgraphs import product_subgraph, support_subgraph


def test_specialists_compile_as_child_graphs() -> None:
    assert "run_product_agent" in product_subgraph.get_graph().nodes
    assert "run_support_agent" in support_subgraph.get_graph().nodes


async def test_explicit_mixed_request_runs_without_a_model_call() -> None:
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="Order ORD102 is late. Show me Sony alternatives too.")
            ],
            "current_query": "Order ORD102 is late. Show me Sony alternatives too.",
            "agent_results": [],
        },
        config={"configurable": {"thread_id": uuid4().hex}},
        context=AgentContext(api_key="unused", model_name="unused"),
    )

    assert result["route"] == ["support_agent", "product_agent"]
    assert "Order ORD102" in result["final_answer"]
    assert "$" in result["final_answer"]
