# AxiomCart — Multi-Agent Shopping Assistant

AxiomCart is a voice-first Python shopping assistant for teaching LangGraph
orchestration. It includes speech input and output, product search, order
support, parallel routing, checkpointed human input, live telemetry, and a
source-backed architecture explorer.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/smakubi/axiomcart-ai-assistant)

## What changed from the original

- Replaced hand-written model/tool loops with LangChain's maintained
  `create_agent()` abstraction.
- Upgraded the parent graph to typed structured routing, `Command`, parallel
  `Send`, reducers, `interrupt()`, and version 2 streaming events.
- Compiled product and support as child graphs that hand results back with
  `Command.PARENT`.
- Removed import-time API-key exits and heavy vector-store initialization.
- Added a FastAPI streaming API that accepts a deployment key or a learner's
  session-only key.
- Uses deterministic graph paths for explicit requests and the open-weight
  Inkling model through Baseten only when a turn needs model reasoning.
- Added a continuous microphone session, turn detection, transcription, and
  spoken responses. Keyboard input remains available as a secondary control.
- Added an architecture page and clickable graph nodes that display the exact
  Python running in the application.
- Added a responsive teaching UI inspired by the clean, two-pane Voice AI demo.
- Made the UI and Python backend deploy together as one Vercel project.

## Architecture

```text
START
  │
  ▼
orchestrator ── structured RoutingDecision
  │
  ├── Send(product_agent subgraph) ── catalog tools ──┐
  │                                                   │
  └── Send(support_agent subgraph) ── interrupt ──────┤
                                                      ▼
                                      Command.PARENT → synthesizer
                                                      │
                                                     END
```

The parent workflow stays explicit in `src/graph.py`. `src/subgraphs.py`
compiles each specialist as a child workflow. Explicit catalog and order
requests take a deterministic tool path; `create_agent()` owns the specialist
model/tool loop when the request needs judgment.

## Run locally

### 1. Install

Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/) are recommended.

```bash
git clone https://github.com/smakubi/axiomcart-ai-assistant.git
cd axiomcart-ai-assistant
uv sync
```

### 2. Start the product

```bash
uv run uvicorn src.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000), allow microphone access,
and press the microphone button. Open [http://localhost:8000/architecture](http://localhost:8000/architecture)
for the source-backed system walkthrough.

You can instead configure a server key:

```bash
cp .env.example .env
# Add BASETEN_API_KEY for Inkling and OPENAI_API_KEY for speech
uv run uvicorn src.api:app --reload
```

### 3. Run the CLI (optional)

```bash
export BASETEN_API_KEY=...
uv run python -m src.main
```

## Good demo prompts

| Prompt | Concept to point out |
| --- | --- |
| `Show me wireless headphones under $300` | One specialist and a catalog tool |
| `Where is order ORD102?` | One specialist and an order lookup |
| `Order ORD102 is late. Show me Sony alternatives too.` | Parallel `Send` fan-out and synthesis |
| `I need help with an order` | `interrupt()` and `Command(resume=...)` |

Sample order IDs are `ORD101` through `ORD104`.

## Project map

```text
api/*.py                 Thin Vercel route entrypoints
public/                  Zero-build web interface
public/architecture.html Source-backed architecture walkthrough
src/api.py               FastAPI routes and NDJSON event stream
src/config.py            Per-run model context; no import-time side effects
src/data.py              Small catalog and order fixtures
src/graph.py             Graph construction and checkpoint injection
src/nodes.py             Orchestrator, specialists, and synthesizer
src/subgraphs.py         Compiled specialist child graphs
src/state.py             Typed shared state and reducers
src/tools.py             Deterministic, structured tools
src/main.py              Optional CLI using the same graph
tests/                   Fast, key-free unit tests
docs/TEACHING_GUIDE.md   A ready-to-use lesson plan
```

## Modern LangGraph patterns in this repo

### Context instead of globals

`AgentContext` carries provider, base URL, API key, and model through the graph's
`context_schema`. Baseten is selected first when its key exists. A learner's
OpenAI key is scoped to one run and is never assigned to a module-level client.

### Structured routing

Explicit commerce intent is routed locally to avoid an unnecessary model round
trip. Ambiguous intent uses a `RoutingDecision` Pydantic model, so the graph
never parses agent names out of free-form text.

### Parallel fan-out and fan-in

The orchestrator returns `Command(goto=[Send(...), ...])`. The
`agent_results` reducer merges writes from specialists that execute in the same
super-step. The synthesizer receives the combined results.

### Specialist subgraphs

Product and support are compiled `StateGraph` child workflows registered as
nodes in the parent. They inherit runtime context and checkpointing, then use
`Command.PARENT` to route their reduced result to the parent synthesizer.

### Maintained agent loops

Product and support specialists use `create_agent()` when a request needs model
judgment. Common catalog and order lookups use the same typed tools directly.
This contrast makes the cost and purpose of an agent loop visible to learners.

### Human-in-the-loop

The support node calls `interrupt()` when no order identifier is present. The
graph checkpoint stores the paused execution. The next API request uses
`Command(resume=...)` and continues from that node.

### Typed version 2 streaming

FastAPI consumes `graph.astream(..., version="v2")` and emits newline-delimited
JSON. Custom events from nodes and tools power the live browser inspector.

### Voice boundaries

The browser keeps one microphone stream open, records a turn with
`MediaRecorder`, and sends it after a short silence. It automatically resumes
listening after the spoken answer. FastAPI uses `gpt-4o-mini-transcribe` and
runs the text through LangGraph. Natural `gpt-4o-mini-tts` PCM speech is streamed
to the browser and begins playing while the remaining audio arrives. The live
trace reports input, transcription, graph, and speech-start duration separately.

### Source-backed architecture

`/api/architecture` uses Python inspection to return the current implementation
of each graph component. Both the live graph cards and `/architecture` consume
that endpoint, so the code shown during a lesson matches the deployed runtime.

## Deploy to Vercel

Click **Deploy with Vercel** above or import the repository in Vercel. No custom
build command is required. Vercel maps the thin files in `api/` to functions;
each imports the same FastAPI application. Files in `public/` are served at the
same origin.

Optional environment variables:

| Variable | Purpose |
| --- | --- |
| `BASETEN_API_KEY` | Default reasoning provider key |
| `BASETEN_MODEL` | Baseten model; defaults to `thinkingmachines/inkling-small` |
| `OPENAI_API_KEY` | Transcription, speech, and reasoning fallback |
| `OPENAI_MODEL` | OpenAI fallback model |
| `LOG_LEVEL` | Python logging level |

The included `vercel.json` gives the graph function a 300-second maximum
duration.

## Persistence note

The zero-infrastructure version uses `InMemorySaver`, which is ideal for local
teaching and warm Vercel instances. Production applications that must resume an
interrupt after a cold start should replace it with a durable checkpointer such
as `AsyncPostgresSaver`. `build_graph(checkpointer=...)` is already injectable
for that upgrade.

## Catalog retrieval note

The catalog tool uses transparent lexical ranking so deployment is fast and the
class can inspect every scoring rule. `search_product_catalog` is intentionally
the retrieval boundary: swap its internals for a vector store without changing
the agent or graph. This makes the architectural lesson separate from the
embedding-database lesson.

## Validation

```bash
uv run ruff check .
uv run pytest
uv run python -m compileall src api
```

## Further reading

- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)

The original PDF instructor guide remains in `instructor_guide/` for provenance;
the current lesson plan is `docs/TEACHING_GUIDE.md`.
