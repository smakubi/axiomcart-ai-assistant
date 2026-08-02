"""Source-backed metadata for the architecture explorer."""

from __future__ import annotations

from inspect import getsource

from src.graph import build_graph
from src.nodes import orchestrator, product_agent, support_agent, synthesizer
from src.state import AxiomCartState, RoutingDecision
from src.tools import escalate_to_human, get_order_status, search_product_catalog


def _component(
    component_id: str,
    title: str,
    role: str,
    concept: str,
    path: str,
    *objects: object,
) -> dict:
    sources = [getsource(getattr(item, "func", item)).strip() for item in objects]
    return {
        "id": component_id,
        "title": title,
        "role": role,
        "concept": concept,
        "path": path,
        "source": "\n\n".join(sources),
    }


def architecture_manifest() -> dict:
    """Return architecture stages and the exact Python used by each component."""
    return {
        "voice_pipeline": [
            {
                "id": "audio-input",
                "title": "Audio input",
                "detail": "MediaRecorder captures a short browser recording.",
                "technology": "MediaRecorder",
            },
            {
                "id": "transcription",
                "title": "Transcription",
                "detail": "OpenAI converts the recording to text for the graph.",
                "technology": "gpt-transcribe",
            },
            {
                "id": "reasoning",
                "title": "Graph execution",
                "detail": "Inkling routes the request and runs the relevant specialists.",
                "technology": "LangGraph + Inkling",
            },
            {
                "id": "speech-output",
                "title": "Speech output",
                "detail": "OpenAI produces the spoken answer returned to the browser.",
                "technology": "gpt-4o-mini-tts",
            },
        ],
        "graph_flow": [
            ["START", "orchestrator"],
            ["orchestrator", "product_agent"],
            ["orchestrator", "support_agent"],
            ["product_agent", "synthesizer"],
            ["support_agent", "synthesizer"],
            ["synthesizer", "END"],
        ],
        "components": [
            _component(
                "graph",
                "Graph builder",
                "Registers nodes, state, context, edges, and checkpointing.",
                "StateGraph + InMemorySaver",
                "src/graph.py",
                build_graph,
            ),
            _component(
                "orchestrator",
                "Orchestrator",
                "Produces a validated routing decision and fans work out in parallel.",
                "with_structured_output + Command + Send",
                "src/nodes.py",
                orchestrator,
            ),
            _component(
                "product_agent",
                "Product agent",
                "Runs the catalog specialist with LangChain's maintained agent loop.",
                "create_agent + search_product_catalog",
                "src/nodes.py",
                product_agent,
            ),
            _component(
                "support_agent",
                "Support agent",
                "Looks up orders and pauses for missing customer information.",
                "create_agent + interrupt",
                "src/nodes.py",
                support_agent,
            ),
            _component(
                "synthesizer",
                "Synthesizer",
                "Combines parallel specialist results into one concise response.",
                "Reducer fan-in",
                "src/nodes.py",
                synthesizer,
            ),
            _component(
                "state",
                "Typed state",
                "Defines the shared graph contract and structured routing schema.",
                "MessagesState + Pydantic",
                "src/state.py",
                RoutingDecision,
                AxiomCartState,
            ),
            _component(
                "tools",
                "Tools",
                "Keeps catalog, order, and escalation side effects behind typed boundaries.",
                "LangChain @tool",
                "src/tools.py",
                search_product_catalog,
                get_order_status,
                escalate_to_human,
            ),
        ],
    }
