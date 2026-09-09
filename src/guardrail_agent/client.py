"""Thin wrapper around the Anthropic SDK.

Every call returns both the parsed result and a token-usage tuple so the agent
can accumulate cost/latency for the evaluation suite. All JSON parsing is
defensive: a malformed model response raises ``ModelResponseError`` which the
guardrails treat as fail-closed.
"""

from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from guardrail_agent.config import SETTINGS
from guardrail_agent.offline import offline_enabled, offline_json

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class ModelResponseError(RuntimeError):
    """Raised when the model output cannot be parsed into the expected shape."""


_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        SETTINGS.require_api_key()
        _client = anthropic.Anthropic()
    return _client


def _extract_json(text: str) -> dict[str, Any]:
    for candidate in (text, *_FENCE.findall(text)):
        m = _OBJECT.search(candidate)
        if not m:
            continue
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
    raise ModelResponseError(f"no parseable JSON object in model output: {text[:200]!r}")


def complete_json(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int = 1024,
) -> tuple[dict[str, Any], tuple[int, int]]:
    """Return (parsed_object, (input_tokens, output_tokens))."""
    if offline_enabled():
        return offline_json(system=system, user=user), (0, 0)
    resp = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system + "\n\nRespond with a single JSON object and nothing else.",
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    usage = (resp.usage.input_tokens, resp.usage.output_tokens)
    return _extract_json(text), usage


def complete_text(
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int = 1024,
) -> tuple[str, tuple[int, int]]:
    if offline_enabled():
        return "", (0, 0)
    resp = get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    usage = (resp.usage.input_tokens, resp.usage.output_tokens)
    return text, usage
