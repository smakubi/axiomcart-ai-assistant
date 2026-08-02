"""Deterministic tools used by the two specialist agents.

Tools return structured dictionaries so both the model and the teaching UI can
inspect them. Catalog retrieval intentionally stays local and transparent; the
``search_product_catalog`` boundary is the exact place to plug in a vector DB.
"""

from __future__ import annotations

import re
from contextlib import suppress
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from langchain.tools import tool
from langgraph.config import get_stream_writer

from src.data import ESCALATION_QUEUE, ORDER_DATABASE, PRODUCT_CATALOG

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _emit(tool_name: str, detail: str) -> None:
    """Publish a tool event when called inside a streaming graph run."""
    with suppress(LookupError, RuntimeError):
        get_stream_writer()(
            {
                "kind": "tool",
                "node": tool_name,
                "status": "active",
                "detail": detail,
            }
        )


def _tokens(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


def _searchable_text(product: dict) -> str:
    fields = [
        product["name"],
        product["brand"],
        product["category"],
        product["description"],
        *product["features"],
        *product["colors"],
    ]
    return " ".join(fields)


def rank_products(query: str, *, limit: int = 3) -> list[dict]:
    """Rank the catalog with readable lexical scoring and price filters."""
    query_tokens = _tokens(query)
    budget_match = re.search(r"(?:under|below|less than)\s*[$]?\s*([\d,]+)", query.lower())
    budget = int(budget_match.group(1).replace(",", "")) if budget_match else None

    ranked: list[tuple[float, dict]] = []
    for product in PRODUCT_CATALOG:
        product_tokens = _tokens(_searchable_text(product))
        overlap = query_tokens & product_tokens
        exact_brand = product["brand"].lower() in query.lower()
        exact_name = product["name"].lower() in query.lower()
        score = len(overlap) + (3 if exact_brand else 0) + (5 if exact_name else 0)
        if budget is not None and product["price"] <= budget:
            score += 2
        elif budget is not None:
            score -= 3
        if score > 0:
            ranked.append((score + product["rating"] / 10, product))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [product for _, product in ranked[:limit]]


@tool
def search_product_catalog(query: str) -> dict:
    """Search products by category, brand, features, color, and price intent."""
    _emit("search_product_catalog", f"Searching the catalog for “{query}”")
    matches = rank_products(query)
    return {
        "query": query,
        "count": len(matches),
        "products": matches,
        "retrieval": "transparent lexical ranking",
    }


def normalise_order_id(value: str) -> str:
    """Convert ``ord-101`` or ``101`` to the canonical ``ORD101`` form."""
    digits = re.sub(r"\D", "", value)
    return f"ORD{digits}" if digits else value.upper().strip()


def lookup_order(identifier: str) -> tuple[str, dict] | None:
    """Find an order by ID or registered email address."""
    if "@" in identifier:
        email = identifier.lower().strip()
        for order_id, order in ORDER_DATABASE.items():
            if order["customer_email"].lower() == email:
                return order_id, order
        return None

    order_id = normalise_order_id(identifier)
    order = ORDER_DATABASE.get(order_id)
    return (order_id, order) if order else None


@tool
def get_order_status(identifier: str) -> dict:
    """Look up an order using an order ID such as ORD102 or an email address."""
    _emit("get_order_status", f"Looking up {identifier}")
    match = lookup_order(identifier)
    if not match:
        return {"found": False, "identifier": identifier}
    order_id, order = match
    return {"found": True, "order_id": order_id, **order}


@tool
def escalate_to_human(
    order_id: str,
    issue_summary: str,
    priority: Literal["low", "normal", "high", "urgent"] = "normal",
) -> dict:
    """Create a teaching-demo support ticket for an unresolved order issue."""
    canonical_order_id = normalise_order_id(order_id)
    _emit("escalate_to_human", f"Creating a {priority} priority support ticket")
    order = ORDER_DATABASE.get(canonical_order_id, {})
    ticket = {
        "ticket_id": f"ESC-{uuid4().hex[:8].upper()}",
        "created_at": datetime.now(UTC).isoformat(),
        "order_id": canonical_order_id,
        "customer_name": order.get("customer_name", "Unknown"),
        "customer_email": order.get("customer_email", "Unknown"),
        "issue_summary": issue_summary,
        "priority": priority,
        "status": "queued",
    }
    ESCALATION_QUEUE.append(ticket)
    return ticket
