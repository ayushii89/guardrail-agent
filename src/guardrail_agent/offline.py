"""Offline responder: deterministic canned model replies, zero API spend.

Enabled with ``GUARDRAIL_OFFLINE=1``. Every stage of the pipeline still runs;
the LLM calls are replaced with rule-based stand-ins. Answers are built directly
from the retrieved fixture evidence, so they are genuinely grounded, but the
guardrail classifications and judge verdicts are heuristics, not a real model.
Use it for demos and local development, not for measuring model quality.
"""

from __future__ import annotations

import os
import re

_OFF_TOPIC = re.compile(
    r"\b(recipe|quicksort|scrape|scraper|capital of|world cup|weather|"
    r"stock|invest(ment)?|horoscope|python script|linkedin)\b",
    re.I,
)
_EVIDENCE_LINE = re.compile(r"^\[(\d+)\]\s*\(([^)]+)\)\s*([^:]+):\s*(.+)$")
_CLAIM_RE = re.compile(r"\[claim (\d+)\]")


def offline_enabled() -> bool:
    return os.getenv("GUARDRAIL_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def _first_sentence(text: str, limit: int = 200) -> str:
    text = text.strip()
    m = re.search(r"(.+?[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    return out[:limit].rstrip()


def _synthesize(user: str) -> dict:
    evidence: list[tuple[int, str]] = []
    for line in user.splitlines():
        m = _EVIDENCE_LINE.match(line.strip())
        if m:
            evidence.append((int(m.group(1)), m.group(4)))
    if not evidence:
        return {"answerable": False, "claims": []}
    claims = [
        {"text": _first_sentence(text), "citations": [n]}
        for n, text in evidence[:4]
    ]
    return {"answerable": True, "claims": claims}


def _judge_content(user: str) -> dict:
    lowered = user.lower()
    abstain = "abstain case: true" in lowered
    m = re.search(r"expected facts:\s*(\[.*\])", user)
    facts: list[str] = re.findall(r"'([^']+)'|\"([^\"]+)\"", m.group(1)) if m else []
    facts = [a or b for a, b in facts]
    answer = user.split("Expected facts:")[0].lower()
    if abstain:
        cues = ("does not answer", "not available", "no evidence")
        correct = any(c in answer for c in cues)
    else:
        correct = all(f.lower() in answer for f in facts) if facts else True
    return {"correct": correct, "grounded": True, "reason": "offline heuristic verdict"}


def offline_json(*, system: str, user: str) -> dict:
    s = system.lower()

    if "input guardrail" in s:
        blocked = bool(_OFF_TOPIC.search(user))
        return {
            "allowed": not blocked,
            "violated_policies": ["out_of_scope"] if blocked else [],
            "severity": "medium" if blocked else "none",
            "rationale": "off-topic for the project-status domain" if blocked else "in scope",
        }

    if "break a user's question" in s or "sub-questions" in s:
        parts = re.split(r"\s+and\s+|,\s*", user.strip().rstrip("?"))
        subs = [p.strip() for p in parts if len(p.strip()) > 3][:4] or [user]
        return {"subquestions": [{"question": q, "connectors": []} for q in subs]}

    if "verify citations" in s:
        idx = [int(n) for n in _CLAIM_RE.findall(user)]
        return {"verdicts": [{"index": i, "supported": True, "reason": "offline"} for i in idx]}

    if "grade an assistant's answer" in s:
        return _judge_content(user)

    if "numbered evidence" in s:
        return _synthesize(user)

    return {}
