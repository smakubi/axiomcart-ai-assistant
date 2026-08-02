"""Compile the product and support specialists as reusable child graphs."""

from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import START, StateGraph

from src.config import AgentContext
from src.nodes import product_agent, support_agent
from src.state import WorkerState


def build_specialist_subgraph(name: str, worker: Callable):
    """Wrap one specialist in a child graph that inherits parent context and state."""
    builder = StateGraph(WorkerState, context_schema=AgentContext)
    builder.add_node(name, worker)
    builder.add_edge(START, name)
    return builder.compile()


product_subgraph = build_specialist_subgraph("run_product_agent", product_agent)
support_subgraph = build_specialist_subgraph("run_support_agent", support_agent)
