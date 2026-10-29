"""LLM provider adapter. Without ANTHROPIC_API_KEY the app uses only the deterministic engine.

The model is used for phrasing/ranking help on open-ended recommendation questions ONLY. Safety-relevant
facts (allergens, ingredients, price, availability) are always answered deterministically from menu data.
Every dish id the model returns is validated against the restaurant's candidate set.
"""
from __future__ import annotations

import json
import logging

import httpx

from ..config import get_settings

log = logging.getLogger("foodmania.llm")


class LLMProvider:
    name = "none"

    def complete(self, system: str, user: str) -> dict | None:  # pragma: no cover - interface
        return None


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def complete(self, system: str, user: str) -> dict | None:
        s = get_settings()
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": s.anthropic_api_key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": s.llm_model, "max_tokens": 500, "system": system, "messages": [{"role": "user", "content": user}]},
                timeout=s.llm_timeout_seconds,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start : end + 1]) if start >= 0 else None
        except Exception as e:  # timeouts, HTTP errors, bad JSON -> graceful fallback
            log.warning("llm_unavailable: %s", type(e).__name__)
            return None


def get_llm() -> LLMProvider:
    return AnthropicProvider() if get_settings().anthropic_api_key else LLMProvider()
