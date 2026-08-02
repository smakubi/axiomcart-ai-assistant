"""Runtime configuration for AxiomCart.

This module deliberately performs no validation at import time. The web app can
therefore boot without a key and let each learner provide one in the UI.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

BASETEN_BASE_URL = "https://inference.baseten.co/v1"
DEFAULT_BASETEN_MODEL = "thinkingmachines/inkling-small"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_MODEL = DEFAULT_BASETEN_MODEL


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
    provider: str = "baseten"
    base_url: str | None = BASETEN_BASE_URL


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Resolved provider settings for one graph run."""

    api_key: str
    model_name: str
    provider: str
    base_url: str | None = None


def server_model_config() -> ModelConfig | None:
    """Prefer the deployment's open-weight model, then fall back to OpenAI."""
    baseten_key = os.getenv("BASETEN_API_KEY", "").strip()
    if baseten_key:
        return ModelConfig(
            api_key=baseten_key,
            model_name=os.getenv("BASETEN_MODEL", DEFAULT_BASETEN_MODEL).strip()
            or DEFAULT_BASETEN_MODEL,
            provider="baseten",
            base_url=BASETEN_BASE_URL,
        )

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        return ModelConfig(
            api_key=openai_key,
            model_name=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
            or DEFAULT_OPENAI_MODEL,
            provider="openai",
        )
    return None


def server_api_key() -> str | None:
    """Return the deployment-level key, if the owner configured one."""
    config = server_model_config()
    return config.api_key if config else None


def speech_api_key() -> str | None:
    """Return the OpenAI key used only for transcription and speech."""
    value = os.getenv("OPENAI_API_KEY", "").strip()
    return value or None


def chat_model(context: AgentContext, *, temperature: float = 0) -> ChatOpenAI:
    """Create an OpenAI-compatible chat model for the selected provider."""
    provider_options = (
        {"reasoning_effort": "minimal", "max_completion_tokens": 1_500}
        if context.provider == "baseten"
        else {}
    )
    return ChatOpenAI(
        api_key=context.api_key,
        model=context.model_name,
        base_url=context.base_url,
        temperature=temperature,
        timeout=60,
        max_retries=2,
        **provider_options,
    )


configure_logging()
