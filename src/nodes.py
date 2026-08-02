"""The four teaching nodes that make up the AxiomCart graph.

Specialists use LangChain's current ``create_agent`` abstraction. The parent
workflow remains explicit so learners can study routing, fan-out, reducers,
interrupts, and synthesis without reading a hand-written tool loop.
"""

from __future__ import annotations

import re
from time import perf_counter
from typing import Literal

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command, Send, interrupt

from src.config import AgentContext, chat_model
from src.data import SUPPORT_POLICIES
from src.state import AgentResult, AgentTask, AxiomCartState, RoutingDecision, WorkerState
from src.tools import escalate_to_human, get_order_status, rank_products, search_product_catalog

PRODUCT_PROMPT = """You are AxiomCart's product discovery specialist.

Use search_product_catalog for every product request. Only recommend products
returned by the tool, format prices in USD with a $ symbol, and be honest when nothing fits.
For greetings or thanks, answer warmly without using a tool. Keep answers clear,
compact, and useful to a shopper. Return plain text without Markdown formatting.
"""

SUPPORT_PROMPT = f"""You are AxiomCart's order support specialist.

Use get_order_status before making claims about an order. Use
escalate_to_human only when the customer asks for a person or the issue cannot
be resolved. Be concise and empathetic.
Return plain text without Markdown formatting.

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
SUPPORT_TERMS = {
    "order",
    "ord",
    "delivery",
    "delayed",
    "late",
    "tracking",
    "shipped",
    "refund",
    "support",
    "human",
}
PRODUCT_TERMS = {
    "product",
    "recommend",
    "show me",
    "under $",
    "alternative",
    "headphone",
    "earbud",
    "shoe",
    "phone",
    "macbook",
    "fan",
    "sony",
    "bose",
    "nike",
    "apple",
    "samsung",
}
COMPLEX_SUPPORT_TERMS = {"refund", "return", "human", "person", "agent", "escalate"}


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


def plain_spoken_text(value: str) -> str:
    """Remove formatting characters that should not reach speech synthesis."""
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"^#{1,6}\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^[*-]\s+", "", value, flags=re.MULTILINE)
    return value.strip()


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


def fallback_routing_decision(query: str) -> RoutingDecision:
    """Keep common shopping routes available when a provider returns invalid JSON."""
    decision = deterministic_routing_decision(query)
    if decision:
        return decision
    return RoutingDecision(
        tasks=[
            AgentTask(agent="product_agent", instruction=f"Handle this customer request: {query}")
        ],
        reasoning="Deterministic fallback assigned the general request to product discovery.",
    )


def deterministic_routing_decision(query: str) -> RoutingDecision | None:
    """Route explicit commerce intent without spending a model round trip."""
    lowered = query.lower()
    agents = []
    if any(term in lowered for term in SUPPORT_TERMS):
        agents.append("support_agent")
    if any(term in lowered for term in PRODUCT_TERMS):
        agents.append("product_agent")
    if not agents:
        return None
    return RoutingDecision(
        tasks=[
            AgentTask(agent=agent, instruction=f"Handle this customer request: {query}")
            for agent in agents
        ],
        reasoning="Explicit commerce intent matched the deterministic low-latency route.",
    )


def format_usd(value: int | float) -> str:
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def format_product_results(payload: dict) -> str:
    """Turn structured catalog results into concise speech without another model call."""
    products = payload.get("products", [])
    if not products:
        return "I couldn't find a catalog match for that request. Try a brand or product category."
    descriptions = [
        f"{product['name']} at {format_usd(product['price'])}, rated {product['rating']} out of 5"
        for product in products
    ]
    lead = "The strongest match is" if len(descriptions) == 1 else "The strongest matches are"
    return f"{lead} " + "; ".join(descriptions) + "."


def format_order_result(payload: dict) -> str:
    """Turn structured order data into a natural status answer without another model call."""
    if not payload.get("found"):
        return f"I couldn't find an order matching {payload.get('identifier', 'that identifier')}."
    answer = (
        f"Order {payload['order_id']} for {payload['product']} is {payload['status'].lower()}. "
        f"The estimated delivery date is {payload['estimated_delivery']}."
    )
    if payload.get("delay_reason"):
        answer += f" The reported delay is due to {payload['delay_reason'].lower()}."
    return answer


async def orchestrator(
    state: AxiomCartState,
    runtime: Runtime[AgentContext],
) -> Command[Literal["product_agent", "support_agent"]]:
    """Classify the newest message and fan out with ``Send``."""
    started_at = perf_counter()
    query = state.get("current_query") or latest_user_text(state["messages"])
    decision = deterministic_routing_decision(query)
    routing_mode = "deterministic"
    if decision:
        emit("orchestrator", "active", "Explicit intent matched; skipping the routing model")
    else:
        routing_mode = "model"
        emit("orchestrator", "active", "Ambiguous intent requires structured model routing")
        router = chat_model(runtime.context).with_structured_output(
            RoutingDecision,
            method="json_schema",
        )
        try:
            decision = await router.ainvoke(
                [SystemMessage(content=ORCHESTRATOR_PROMPT), HumanMessage(content=query)]
            )
        except Exception as error:
            decision = fallback_routing_decision(query)
            routing_mode = "fallback"
            emit(
                "orchestrator",
                "active",
                f"Provider output was invalid ({type(error).__name__}); using fallback routing",
            )
    route = [task.agent for task in decision.tasks]
    emit(
        "orchestrator",
        "complete",
        decision.reasoning,
        route=route,
        mode=routing_mode,
        duration_ms=round((perf_counter() - started_at) * 1000),
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
) -> Command:
    """Run the current LangChain agent loop for catalog discovery."""
    started_at = perf_counter()
    emit("product_agent", "active", "Searching products and drafting guidance")
    direct_matches = rank_products(state["current_query"])
    if direct_matches:
        payload = await search_product_catalog.ainvoke({"query": state["current_query"]})
        answer = format_product_results(payload)
        used_tools = ["search_product_catalog"]
        execution_mode = "deterministic"
    else:
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
        answer = plain_spoken_text(message_text(result["messages"][-1]))
        used_tools = tool_names(result["messages"])
        execution_mode = "agent"
    emit(
        "product_agent",
        "complete",
        "Product specialist finished on the low-latency path"
        if execution_mode == "deterministic"
        else "Product specialist finished with model reasoning",
        tools=used_tools,
        mode=execution_mode,
        duration_ms=round((perf_counter() - started_at) * 1000),
    )
    contribution: AgentResult = {
        "agent": "product_agent",
        "label": "Product discovery",
        "answer": answer,
        "tool_names": used_tools,
    }
    return Command(
        update={"agent_results": [contribution]},
        goto="synthesizer",
        graph=Command.PARENT,
    )


async def support_agent(
    state: WorkerState,
    runtime: Runtime[AgentContext],
) -> Command:
    """Pause for an identifier, then run the support agent and tools."""
    started_at = perf_counter()
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
    identifier = IDENTIFIER_PATTERN.search(f"{context}\n{query}")
    use_direct_path = identifier and not any(
        term in query.lower() for term in COMPLEX_SUPPORT_TERMS
    )
    if use_direct_path:
        payload = await get_order_status.ainvoke({"identifier": identifier.group(0)})
        answer = format_order_result(payload)
        used_tools = ["get_order_status"]
        execution_mode = "deterministic"
    else:
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
        answer = plain_spoken_text(message_text(result["messages"][-1]))
        used_tools = tool_names(result["messages"])
        execution_mode = "agent"
    emit(
        "support_agent",
        "complete",
        "Support specialist finished on the low-latency path"
        if execution_mode == "deterministic"
        else "Support specialist finished with model reasoning",
        tools=used_tools,
        mode=execution_mode,
        duration_ms=round((perf_counter() - started_at) * 1000),
    )
    contribution: AgentResult = {
        "agent": "support_agent",
        "label": "Order support",
        "answer": answer,
        "tool_names": used_tools,
    }
    return Command(
        update={"agent_results": [contribution]},
        goto="synthesizer",
        graph=Command.PARENT,
    )


async def synthesizer(
    state: AxiomCartState,
    runtime: Runtime[AgentContext],
) -> dict:
    """Pass through one result or merge parallel contributions."""
    started_at = perf_counter()
    results = state.get("agent_results", [])
    emit("synthesizer", "active", "Preparing one customer-facing response")

    if not results:
        answer = "I couldn't complete that run. Please try the request again."
    elif len(results) == 1:
        answer = results[0]["answer"]
    else:
        answer = "\n\n".join(result["answer"] for result in results)

    emit(
        "synthesizer",
        "complete",
        "Final answer assembled without an extra model round",
        mode="deterministic",
        duration_ms=round((perf_counter() - started_at) * 1000),
    )
    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}
