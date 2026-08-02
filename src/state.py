"""Typed state and structured outputs for the teaching graph."""

from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

AgentName = Literal["product_agent", "support_agent"]


class AgentTask(BaseModel):
    """One instruction emitted by the orchestrator."""

    agent: AgentName = Field(description="The specialist that should run")
    instruction: str = Field(description="A concise, self-contained assignment")


class RoutingDecision(BaseModel):
    """Provider-validated routing output from the orchestrator."""

    tasks: list[AgentTask] = Field(min_length=1, max_length=2)
    reasoning: str = Field(description="One short teaching-friendly explanation")


class AgentResult(TypedDict):
    """A specialist's contribution to the final response."""

    agent: AgentName
    label: str
    answer: str
    tool_names: list[str]


def merge_agent_results(
    current: list[AgentResult] | None,
    update: list[AgentResult] | None,
) -> list[AgentResult]:
    """Append parallel results; an empty update starts a fresh user turn."""
    if not update:
        return []
    return [*(current or []), *update]


class AxiomCartState(MessagesState):
    """Shared state visible in the UI's live inspector."""

    current_query: str
    routing_reason: str
    route: list[AgentName]
    tasks: list[dict[str, str]]
    agent_results: Annotated[list[AgentResult], merge_agent_results]
    final_answer: str


class WorkerState(TypedDict):
    """Minimal state sent to each parallel specialist with ``Send``."""

    messages: list
    current_query: str
    instruction: str
    agent_results: NotRequired[list[AgentResult]]
