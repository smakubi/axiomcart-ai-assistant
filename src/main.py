"""Small CLI wrapper around the same graph used by the web app."""

from __future__ import annotations

import argparse
import asyncio
import os
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.config import DEFAULT_MODEL, AgentContext
from src.graph import axiomcart_graph


async def ask(message: str, *, api_key: str, model: str, thread_id: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    context = AgentContext(api_key=api_key, model_name=model)
    output = await axiomcart_graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "current_query": message,
            "agent_results": [],
        },
        config=config,
        context=context,
        version="v2",
    )
    while output.interrupts:
        payload = output.interrupts[0].value
        question = (
            payload.get("question", str(payload)) if isinstance(payload, dict) else str(payload)
        )
        answer = input(f"\nAgent asks: {question}\nYou: ").strip()
        output = await axiomcart_graph.ainvoke(
            Command(resume=answer),
            config=config,
            context=context,
            version="v2",
        )
    return output.value.get("final_answer", "")


async def repl(*, api_key: str, model: str) -> None:
    thread_id = uuid4().hex
    print("\nAxiomCart teaching assistant (type 'quit' to exit)\n")
    while True:
        message = input("You: ").strip()
        if not message or message.lower() in {"quit", "exit"}:
            break
        answer = await ask(message, api_key=api_key, model=model, thread_id=thread_id)
        print(f"\nAssistant: {answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AxiomCart LangGraph assistant")
    parser.add_argument("--query", help="Run one query and exit")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY before running the CLI.")
    if args.query:
        answer = ask(args.query, api_key=api_key, model=args.model, thread_id=uuid4().hex)
        print(asyncio.run(answer))
    else:
        asyncio.run(repl(api_key=api_key, model=args.model))


if __name__ == "__main__":
    main()
