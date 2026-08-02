"""The four teaching nodes that make up the AxiomCart graph.

Specialists use LangChain's current ``create_agent`` abstraction. The parent
workflow remains explicit so learners can study routing, fan-out, reducers,
interrupts, and synthesis without reading a hand-written tool loop.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command, Send, interrupt

from src.config import AgentContext, chat_model
from src.data import SUPPORT_POLICIES
from src.state import AgentResult, AxiomCartState, RoutingDecision, WorkerState
from src.tools import escalate_to_human, get_order_status, search_product_catalog

PRODUCT_PROMPT = """You are AxiomCart's product discovery specialist.

Use search_product_catalog for every product request. Only recommend products
returned by the tool, mention prices in INR, and be honest when nothing fits.
For greetings or thanks, answer warmly without using a tool. Keep answers clear,
compact, and useful to a shopper.
"""

SUPPORT_PROMPT = f"""You are AxiomCart's order support specialist.

Use get_order_status before making claims about an order. Use
escalate_to_human only when the customer asks for a person or the issue cannot
be resolved. Be concise and empathetic.

Policies:
{SUPPORT_POLICIES}
"""

ORCHESTRATOR_PROMPT = """You route customer requests to AxiomCart specialists.

- product_agent: catalog search, recommendations, product comparisons, greeting
- support_agent: order status, delivery issues, complaints, human escalation
- mixed requests: create one focused task for each relevant specialist

Return the smallest correct set of tasks. Never route a greeting to support.
"""

IDENTIFIER_PATTERN = re.compile(r"\bORD[- ]?\d+\b|[\w.+-]+@[\w.-]+\.\w+", re.I)


def emit(node: str, status: str, detail: str, **extra: object) -> None:
    """Send a compact event to the live graph inspector."""
    get_stream_writer()({"kind": "node", "node": node, "status": status, "detail": detail, **extra})


def message_text(message: BaseMessage) -> str:
    """Normalize text and content-block responses from chat models."""
    if isinstance(message.content, str):
        return message.content
    blocks = message.content if isinstance(message.content, list) else []
    return "\n".join(
        str(block.get("text", "")) for block in blocks if isinstance(block, dict)
    ).strip()


def latest_user_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message_text(message)
    return ""


def conversation_excerpt(messages: list[BaseMessage], *, turns: int = 8) -> str:
    """Format recent human/assistant turns without exposing tool internals."""
    lines: list[str] = []
    for message in messages[-turns:]:
        if isinstance(message, HumanMessage):
            lines.append(f"Customer: {message_text(message)}")
        elif isinstance(message, AIMessage) and message_text(message):
            lines.append(f"Assistant: {message_text(message)}")
    return "\n".join(lines)


def tool_names(messages: list[BaseMessage]) -> list[str]:
    names: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            name = call.get("name")
            if name and name not in names:
                names.append(name)
    return names


async def orchestrator(
    state: AxiomCartState,
    runtime: Runtime[AgentContext],
) -> Command[Literal["product_agent", "support_agent"]]:
    """Classify the newest message and fan out with ``Send``."""
    query = state.get("current_query") or latest_user_text(state["messages"])
    emit("orchestrator", "active", "Classifying intent with structured output")

    router = chat_model(runtime.context).with_structured_output(
        RoutingDecision,
        method="json_schema",
    )
    decision = await router.ainvoke(
        [SystemMessage(content=ORCHESTRATOR_PROMPT), HumanMessage(content=query)]
    )
    route = [task.agent for task in decision.tasks]
    emit(
        "orchestrator",
        "complete",
        decision.reasoning,
        route=route,
    )

    destinations = [
        Send(
            task.agent,
            {
                "messages": state["messages"],
                "current_query": query,
                "instruction": task.instruction,
            },
        )
        for task in decision.tasks
    ]
    return Command(
        update={
            "current_query": query,
            "routing_reason": decision.reasoning,
            "route": route,
            "tasks": [task.model_dump() for task in decision.tasks],
            "agent_results": [],
            "final_answer": "",
        },
        goto=destinations,
    )


async def product_agent(
    state: WorkerState,
    runtime: Runtime[AgentContext],
) -> Command[Literal["synthesizer"]]:
    """Run the current LangChain agent loop for catalog discovery."""
    emit("product_agent", "active", "Searching products and drafting guidance")
    agent = create_agent(
        model=chat_model(runtime.context, temperature=0.2),
        tools=[search_product_catalog],
        system_prompt=PRODUCT_PROMPT,
        name="product_agent",
    )
    prompt = (
        f"Assignment: {state['instruction']}\n"
        f"Customer request: {state['current_query']}\n\n"
        f"Recent conversation:\n{conversation_excerpt(state['messages'])}"
    )
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    answer = message_text(result["messages"][-1])
    used_tools = tool_names(result["messages"])
    emit(
        "product_agent",
        "complete",
        "Product specialist finished",
        tools=used_tools,
    )
    contribution: AgentResult = {
        "agent": "product_agent",
        "label": "Product discovery",
        "answer": answer,
        "tool_names": used_tools,
    }
    return Command(update={"agent_results": [contribution]}, goto="synthesizer")


async def support_agent(
    state: WorkerState,
    runtime: Runtime[AgentContext],
) -> Command[Literal["synthesizer"]]:
    """Pause for an identifier, then run the support agent and tools."""
    query = state["current_query"]
    context = conversation_excerpt(state["messages"])
    combined = f"{context}\n{query}"
    if not IDENTIFIER_PATTERN.search(combined):
        emit("support_agent", "waiting", "Human input required before order lookup")
        supplied = interrupt(
            {
                "kind": "missing_order_identifier",
                "question": "What is your order ID (for example, ORD102) or registered email?",
                "requested": ["order_id", "email"],
            }
        )
        query = f"{query}\nCustomer supplied identifier: {supplied}"

    emit("support_agent", "active", "Checking order context and support policy")
    agent = create_agent(
        model=chat_model(runtime.context, temperature=0.1),
        tools=[get_order_status, escalate_to_human],
        system_prompt=SUPPORT_PROMPT,
        name="support_agent",
    )
    prompt = (
        f"Assignment: {state['instruction']}\n"
        f"Customer request: {query}\n\n"
        f"Recent conversation:\n{context}"
    )
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    answer = message_text(result["messages"][-1])
    used_tools = tool_names(result["messages"])
    emit(
        "support_agent",
        "complete",
        "Support specialist finished",
        tools=used_tools,
    )
    contribution: AgentResult = {
        "agent": "support_agent",
        "label": "Order support",
        "answer": answer,
        "tool_names": used_tools,
    }
    return Command(update={"agent_results": [contribution]}, goto="synthesizer")


async def synthesizer(
    state: AxiomCartState,
    runtime: Runtime[AgentContext],
) -> dict:
    """Pass through one result or merge parallel contributions."""
    results = state.get("agent_results", [])
    emit("synthesizer", "active", "Preparing one customer-facing response")

    if not results:
        answer = "I couldn't complete that run. Please try the request again."
    elif len(results) == 1:
        answer = results[0]["answer"]
    else:
        prompt = (
            "Combine these specialist answers into one concise, natural reply. "
            "Preserve every important order fact and product price. Do not mention "
            "agents, routing, tools, or synthesis.\n\n"
            f"Customer request: {state['current_query']}\n\n"
            f"Specialist results:\n{json.dumps(results, indent=2, ensure_ascii=False)}"
        )
        response = await chat_model(runtime.context, temperature=0.2).ainvoke(prompt)
        answer = message_text(response)

    emit("synthesizer", "complete", "Final answer ready")
    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
