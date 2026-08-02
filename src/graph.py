"""Build the explicit parent graph used by the CLI and web API."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.config import AgentContext
from src.nodes import orchestrator, product_agent, support_agent, synthesizer
from src.state import AxiomCartState


def build_graph(*, checkpointer=None):
    """Compile the graph with an injectable checkpointer for easy testing."""
    builder = StateGraph(AxiomCartState, context_schema=AgentContext)
    builder.add_node("orchestrator", orchestrator)
    builder.add_node("product_agent", product_agent)
    builder.add_node("support_agent", support_agent)
    builder.add_node("synthesizer", synthesizer)
    builder.add_edge(START, "orchestrator")
    builder.add_edge("synthesizer", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


axiomcart_graph = build_graph()
