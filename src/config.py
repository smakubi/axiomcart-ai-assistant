"""Runtime configuration for AxiomCart.

This module deliberately performs no validation at import time. The web app can
therefore boot without a key and let each learner provide one in the UI.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

DEFAULT_MODEL = "gpt-5.4-mini"


def configure_logging() -> None:
    """Install a compact log format once for CLI and server runtimes."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Per-run dependencies passed through LangGraph's context schema."""

    api_key: str
    model_name: str = DEFAULT_MODEL


def server_api_key() -> str | None:
    """Return the deployment-level key, if the owner configured one."""
    value = os.getenv("OPENAI_API_KEY", "").strip()
    return value or None


def chat_model(context: AgentContext, *, temperature: float = 0) -> ChatOpenAI:
    """Create an OpenAI chat model without storing learner keys globally."""
    return ChatOpenAI(
        api_key=context.api_key,
        model=context.model_name,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


configure_logging()
