"""Source-backed metadata for the architecture explorer."""

from __future__ import annotations

from inspect import getsource

from src.graph import build_graph
from src.nodes import (
    deterministic_routing_decision,
    format_order_result,
    format_product_results,
    orchestrator,
    product_agent,
    support_agent,
    synthesizer,
)
from src.state import AxiomCartState, RoutingDecision
from src.subgraphs import build_specialist_subgraph
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
                "detail": "The browser keeps one microphone session open and detects each turn.",
                "technology": "MediaRecorder",
            },
            {
                "id": "transcription",
                "title": "Transcription",
                "detail": "OpenAI converts the recording to text for the graph.",
                "technology": "gpt-4o-mini-transcribe",
            },
            {
                "id": "reasoning",
                "title": "Graph execution",
                "detail": "Explicit requests take a deterministic path; Inkling handles ambiguity.",
                "technology": "LangGraph + optional Inkling",
            },
            {
                "id": "speech-output",
                "title": "Speech output",
                "detail": "Natural PCM speech begins playing while the remaining bytes arrive.",
                "technology": "streamed gpt-4o-mini-tts",
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
                deterministic_routing_decision,
                orchestrator,
            ),
            _component(
                "subgraphs",
                "Specialist subgraphs",
                "Compiles each specialist as a child workflow that inherits parent context "
                "and returns results with Command.PARENT.",
                "StateGraph + Command.PARENT",
                "src/subgraphs.py",
                build_specialist_subgraph,
                product_agent,
            ),
            _component(
                "product_agent",
                "Product agent",
                "Runs the catalog specialist with LangChain's maintained agent loop.",
                "create_agent + search_product_catalog",
                "src/nodes.py",
                format_product_results,
                product_agent,
            ),
            _component(
                "support_agent",
                "Support agent",
                "Looks up orders and pauses for missing customer information.",
                "create_agent + interrupt",
                "src/nodes.py",
                format_order_result,
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
