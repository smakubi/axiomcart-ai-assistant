"""FastAPI application serving the teaching UI and streaming graph API."""

from __future__ import annotations

import json
import os
import platform
from collections.abc import AsyncIterator
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.architecture import architecture_manifest
from src.config import (
    DEFAULT_OPENAI_MODEL,
    AgentContext,
    ModelConfig,
    server_model_config,
    speech_api_key,
)
from src.graph import axiomcart_graph

ROOT_DIR = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT_DIR / "public"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
SPEECH_MODEL = "gpt-4o-mini-tts"
SPEECH_VOICE = "marin"
SPEECH_CHUNK_BYTES = 4_096
SPEECH_SAMPLE_RATE = 24_000

app = FastAPI(
    title="AxiomCart Teaching API",
    description="A LangGraph multi-agent shopping assistant.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

if not os.getenv("VERCEL") and PUBLIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets")


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=4_000)
    resume: str | None = Field(default=None, max_length=1_000)
    thread_id: str = Field(default_factory=lambda: uuid4().hex, max_length=128)
    model: str = Field(default=DEFAULT_OPENAI_MODEL, min_length=1, max_length=100)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=30)


class ResetRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def encode_event(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, default=str) + "\n").encode()


def interrupt_payload(value: object) -> dict | None:
    if isinstance(value, dict) and value.get("question"):
        return value
    if isinstance(value, str):
        return {"kind": "human_input", "question": value}
    return None


def find_interrupt(data: object) -> dict | None:
    if not isinstance(data, dict):
        return None
    raw_interrupts = data.get("__interrupt__")
    if raw_interrupts:
        first = raw_interrupts[0]
        return interrupt_payload(getattr(first, "value", first))
    for update in data.values():
        found = find_interrupt(update)
        if found:
            return found
    return None


def history_messages(history: list[HistoryMessage]):
    messages = []
    for item in history:
        message_type = HumanMessage if item.role == "user" else AIMessage
        messages.append(message_type(content=item.content))
    return messages


async def has_checkpoint(thread_id: str) -> bool:
    snapshot = await axiomcart_graph.aget_state({"configurable": {"thread_id": thread_id}})
    return bool(snapshot.values)


async def graph_events(
    request: ChatRequest,
    model_config: ModelConfig,
) -> AsyncIterator[bytes]:
    started_at = perf_counter()
    run_id = uuid4().hex
    config = {"configurable": {"thread_id": request.thread_id}}
    context = AgentContext(
        api_key=model_config.api_key,
        model_name=model_config.model_name,
        provider=model_config.provider,
        base_url=model_config.base_url,
    )
    yield encode_event(
        {
            "type": "run.started",
            "run_id": run_id,
            "thread_id": request.thread_id,
            "model": model_config.model_name,
            "provider": model_config.provider,
            "elapsed_ms": 0,
        }
    )

    if request.resume is not None:
        graph_input = Command(resume=request.resume)
    else:
        messages = []
        if request.history and not await has_checkpoint(request.thread_id):
            messages.extend(history_messages(request.history))
        messages.append(HumanMessage(content=request.message.strip()))
        graph_input = {
            "messages": messages,
            "current_query": request.message.strip(),
            "agent_results": [],
        }

    final_answer = ""
    route: list[str] = []
    routing_reason = ""
    results: list[dict] = []
    pending_interrupt: dict | None = None

    try:
        async for part in axiomcart_graph.astream(
            graph_input,
            config=config,
            context=context,
            stream_mode=["updates", "custom"],
            subgraphs=True,
            version="v2",
        ):
            part_type = part.get("type")
            data = part.get("data")
            if part_type == "custom" and isinstance(data, dict):
                yield encode_event(
                    {
                        "type": "graph.event",
                        "elapsed_ms": round((perf_counter() - started_at) * 1000),
                        **data,
                    }
                )
                continue
            if part_type != "updates" or not isinstance(data, dict):
                continue

            found_interrupt = find_interrupt(data)
            if found_interrupt:
                pending_interrupt = found_interrupt

            for node_update in data.values():
                if not isinstance(node_update, dict):
                    continue
                final_answer = node_update.get("final_answer", final_answer)
                route = node_update.get("route", route)
                routing_reason = node_update.get("routing_reason", routing_reason)
                if node_update.get("agent_results"):
                    results.extend(node_update["agent_results"])

        if pending_interrupt:
            yield encode_event(
                {
                    "type": "run.interrupted",
                    "run_id": run_id,
                    "thread_id": request.thread_id,
                    "elapsed_ms": round((perf_counter() - started_at) * 1000),
                    **pending_interrupt,
                }
            )
            return

        snapshot = await axiomcart_graph.aget_state(config)
        values = snapshot.values
        final_answer = values.get("final_answer", final_answer)
        route = values.get("route", route)
        routing_reason = values.get("routing_reason", routing_reason)
        results = values.get("agent_results", results)
        yield encode_event(
            {
                "type": "run.completed",
                "run_id": run_id,
                "thread_id": request.thread_id,
                "answer": final_answer,
                "route": route,
                "routing_reason": routing_reason,
                "agent_results": results,
                "elapsed_ms": round((perf_counter() - started_at) * 1000),
            }
        )
    except Exception as error:
        yield encode_event(
            {
                "type": "run.error",
                "run_id": run_id,
                "message": str(error),
                "elapsed_ms": round((perf_counter() - started_at) * 1000),
            }
        )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> HTMLResponse:
    return HTMLResponse((PUBLIC_DIR / "index.html").read_text())


@app.get("/architecture", response_class=HTMLResponse, include_in_schema=False)
async def architecture_page() -> HTMLResponse:
    return HTMLResponse((PUBLIC_DIR / "architecture.html").read_text())


@app.get("/api/health")
async def health() -> dict:
    model_config = server_model_config()
    return {
        "status": "ready",
        "server_key_configured": bool(model_config),
        "speech_configured": bool(speech_api_key()),
        "provider": model_config.provider if model_config else None,
        "model": model_config.model_name if model_config else None,
        "python": platform.python_version(),
        "langgraph": package_version("langgraph"),
        "langchain": package_version("langchain"),
        "transcription_model": TRANSCRIPTION_MODEL,
        "speech_model": SPEECH_MODEL,
        "speech_voice": SPEECH_VOICE,
    }


@app.get("/api/graph")
async def graph_metadata() -> dict:
    return {
        "nodes": [
            {"id": "orchestrator", "label": "Orchestrator", "concept": "structured output"},
            {"id": "product_agent", "label": "Product agent", "concept": "create_agent + tools"},
            {"id": "support_agent", "label": "Support agent", "concept": "interrupt + resume"},
            {"id": "synthesizer", "label": "Synthesizer", "concept": "fan-in"},
        ],
        "edges": [
            ["orchestrator", "product_agent"],
            ["orchestrator", "support_agent"],
            ["product_agent", "synthesizer"],
            ["support_agent", "synthesizer"],
        ],
        "examples": [
            "Show me wireless headphones under $300",
            "Where is order ORD102?",
            "Order ORD102 is late. Show me Sony alternatives too.",
            "I need help with an order",
        ],
    }


@app.get("/api/architecture")
async def architecture_metadata() -> dict:
    return architecture_manifest()


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> StreamingResponse:
    if learner_key and learner_key.strip():
        model_config = ModelConfig(
            api_key=learner_key.strip(),
            model_name=request.model,
            provider="openai",
        )
    else:
        model_config = server_model_config()
    if not model_config:
        raise HTTPException(
            status_code=401,
            detail="Configure BASETEN_API_KEY or add an OpenAI API key in Settings.",
        )
    if request.resume is None and not request.message.strip():
        raise HTTPException(status_code=422, detail="message cannot be empty")
    return StreamingResponse(
        graph_events(request, model_config),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def resolve_speech_key(learner_key: str | None) -> str:
    api_key = (learner_key or speech_api_key() or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Voice requires an OpenAI key in Settings or OPENAI_API_KEY on the server.",
        )
    return api_key


@app.post("/api/voice/transcribe")
async def transcribe_audio(
    audio: Annotated[UploadFile, File()],
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> dict:
    started_at = perf_counter()
    contents = await audio.read(MAX_AUDIO_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Record some audio first.")
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Keep recordings under 10 MB.")

    client = AsyncOpenAI(api_key=resolve_speech_key(learner_key))
    transcription = await client.audio.transcriptions.create(
        model=TRANSCRIPTION_MODEL,
        file=(audio.filename or "recording.webm", contents, audio.content_type or "audio/webm"),
        language="en",
    )
    return {
        "text": transcription.text.strip(),
        "latency_ms": round((perf_counter() - started_at) * 1000),
    }


async def speech_audio(text: str, api_key: str) -> AsyncIterator[bytes]:
    """Stream natural speech bytes as OpenAI produces them."""
    client = AsyncOpenAI(api_key=api_key)
    async with client.audio.speech.with_streaming_response.create(
        model=SPEECH_MODEL,
        voice=SPEECH_VOICE,
        input=text,
        instructions=(
            "Speak with a warm, natural, confident retail-assistant voice. "
            "Use conversational pacing and avoid an announcer-like delivery."
        ),
        response_format="pcm",
        stream_format="audio",
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=SPEECH_CHUNK_BYTES):
            yield chunk


@app.post("/api/voice/speak")
async def speak_text(
    request: SpeechRequest,
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> StreamingResponse:
    api_key = resolve_speech_key(learner_key)
    return StreamingResponse(
        speech_audio(request.text, api_key),
        media_type="audio/pcm",
        headers={
            "Cache-Control": "no-store",
            "X-Speech-Model": SPEECH_MODEL,
            "X-Speech-Voice": SPEECH_VOICE,
            "X-Audio-Sample-Rate": str(SPEECH_SAMPLE_RATE),
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/reset")
async def reset_thread(request: ResetRequest) -> dict:
    thread_id = request.thread_id
    await axiomcart_graph.aupdate_state(
        {"configurable": {"thread_id": thread_id}},
        {
            "messages": [],
            "current_query": "",
            "route": [],
            "tasks": [],
            "agent_results": [],
            "final_answer": "",
        },
    )
    return {"reset": True, "thread_id": thread_id}
