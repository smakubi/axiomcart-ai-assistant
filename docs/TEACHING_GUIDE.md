# Teaching AxiomCart

This guide is designed for a 60–75 minute live class. Use the demo, live graph,
and `/architecture` source explorer as the visual aids.

## Learning goals

By the end, learners should be able to explain:

1. Why an agent needs both model autonomy and deterministic workflow structure.
2. How LangGraph state moves between nodes.
3. Why reducers are required when parallel branches write the same key.
4. How `Send` creates parallel work and how branches converge.
5. How a compiled subgraph becomes a node in a parent workflow.
6. What a checkpointer stores and why `interrupt()` depends on it.
7. How streamed graph events become a responsive product interface.
8. Where voice transcription and speech synthesis sit outside the graph.
9. How runtime code can be presented directly inside a teaching interface.

## Before class

```bash
uv sync
uv run pytest
uv run uvicorn src.api:app --reload
```

Open `http://localhost:8000`, allow microphone access, and speak these four
prompts:

- `Show me wireless headphones under $300`
- `Where is order ORD102?`
- `Order ORD102 is late. Show me Sony alternatives too.`
- `I need help with an order`

## Suggested lesson flow

### 0–10 min — Product first

Speak a product query without showing code. Ask the class to describe what they
think happened. Switch the inspector from **Graph** to **Events** and replay the
sequence.

Key idea: a polished UI can expose system behavior without exposing private
chain-of-thought.

### 10–20 min — State is the contract

Open **Architecture**, then select **Typed state**.

- `AxiomCartState` is shared by the parent graph.
- `WorkerState` is the smaller payload sent to specialists.
- `merge_agent_results` is a reducer, not a normal assignment.

Run the mixed prompt and point to `agent_results` in the State tab.

### 20–32 min — Structured routing and parallel Send

Select the live **Orchestrator** graph card to open its deployed Python source.

1. The model returns `RoutingDecision`, not prose that must be parsed.
2. Each `AgentTask` becomes a `Send` payload.
3. One task routes to one branch; two tasks run in the same super-step.
4. `Command` combines state updates and control flow in one return value.

Run the mixed prompt again. Product and support cards should become active
without a fixed sequence.

### 32–44 min — Subgraphs, agents, and tools

Click **Specialist subgraphs**, then compare **Product agent** and **Tools**.

Contrast three responsibilities:

- LangGraph owns workflow topology and shared state.
- A compiled child graph packages one specialist workflow as a parent node.
- `create_agent()` owns the specialist's model/tool loop.

Show how `Command.PARENT` returns a reduced result to the parent synthesizer,
and how the parent's checkpointer propagates into each child graph.

The catalog search is deterministic so the class can read its ranking logic.
Discuss how a vector database could replace the implementation while preserving
the tool contract.

### 44–56 min — Interrupt and resume

Send `I need help with an order`.

The support card pauses. Show the checkpoint label in the State tab, then enter
`ORD102`.

Explain three rules:

1. A checkpointer is required.
2. Code before `interrupt()` can run again after resume; avoid non-idempotent
   side effects there.
3. Resume with `Command(resume=value)`, not a new conversation input.

### 56–65 min — Streaming into a UI

Open the **Events** and **State** tabs. Point out provider, model, elapsed time,
node status, and tool events while a spoken request runs.

The backend streams two categories:

- version 2 LangGraph `updates`
- explicit `custom` node/tool events

The UI maps these events to visible status changes. It does not need to know how
the model made its private token-level decision.

### 65–75 min — Deploy and extend

Use the Vercel button in the README. Ask learners to choose one extension:

- replace catalog ranking with a vector store;
- replace fixture orders with Postgres;
- use a durable Postgres checkpointer;
- add a third specialist and update `RoutingDecision`;
- render product tool output as cards instead of prose.

## Whiteboard questions

- What happens if both specialists assign `agent_results` without a reducer?
- Why is the orchestrator a workflow node rather than another autonomous agent?
- Which data belongs in graph state, runtime context, or a long-term store?
- When is `create_agent()` enough, and when do you need a custom subgraph?
- What changes when an in-memory checkpointer moves to Postgres?

## Common misconceptions

**“Multi-agent” means every node needs a different model.**  
No. The separation is about responsibilities, prompts, tools, and state—not
necessarily providers.

**Streaming means exposing chain-of-thought.**  
No. Stream status, tool activity, validated state updates, and final output.

**A checkpointer is long-term memory.**  
Not exactly. It stores thread checkpoints. Cross-thread user memory belongs in a
LangGraph Store or application database.

**A Vercel deployment makes in-memory state durable.**  
No. Warm instances can reuse it, but a cold start needs an external checkpointer
for reliable resume behavior.
