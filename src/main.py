"""Small CLI wrapper around the same graph used by the web app."""

from __future__ import annotations

import argparse
import asyncio
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.config import AgentContext, ModelConfig, server_model_config
from src.graph import axiomcart_graph


async def ask(message: str, *, model_config: ModelConfig, thread_id: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    context = AgentContext(
        api_key=model_config.api_key,
        model_name=model_config.model_name,
        provider=model_config.provider,
        base_url=model_config.base_url,
    )
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


async def repl(*, model_config: ModelConfig) -> None:
    thread_id = uuid4().hex
    print("\nAxiomCart teaching assistant (type 'quit' to exit)\n")
    while True:
        message = input("You: ").strip()
        if not message or message.lower() in {"quit", "exit"}:
            break
        answer = await ask(message, model_config=model_config, thread_id=thread_id)
        print(f"\nAssistant: {answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AxiomCart LangGraph assistant")
    parser.add_argument("--query", help="Run one query and exit")
    parser.add_argument("--model", help="Override the configured provider's model")
    args = parser.parse_args()
    model_config = server_model_config()
    if not model_config:
        raise SystemExit("Set BASETEN_API_KEY or OPENAI_API_KEY before running the CLI.")
    if args.model:
        model_config = ModelConfig(
            api_key=model_config.api_key,
            model_name=args.model,
            provider=model_config.provider,
            base_url=model_config.base_url,
        )
    if args.query:
        answer = ask(args.query, model_config=model_config, thread_id=uuid4().hex)
        print(asyncio.run(answer))
    else:
        asyncio.run(repl(model_config=model_config))


if __name__ == "__main__":
    main()
