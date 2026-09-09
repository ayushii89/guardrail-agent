"""PII detection and redaction.

Deterministic regex-based redaction runs on every piece of retrieved evidence
before it reaches the synthesis model, and again on the final answer text. This
is intentionally not model-based: PII redaction must be predictable and testable.
"""

from __future__ import annotations

import re

from guardrail_agent.schema import Evidence

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    (
        "PHONE",
        re.compile(r"(?<!\w)(?:\+?\d{1,2}[ -])?(?:\(?\d{3}\)?[ -])\d{3}[ -]\d{4}(?!\w)"),
    ),
]


def scan_pii(text: str) -> list[str]:
    """Return the kinds of PII present in ``text`` (deduped, ordered)."""
    found: list[str] = []
    for kind, pat in _PATTERNS:
        if pat.search(text) and kind not in found:
            found.append(kind)
    return found


def redact_text(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, kinds_redacted)."""
    kinds: list[str] = []
    out = text
    for kind, pat in _PATTERNS:
        if pat.search(out):
            out = pat.sub(f"[REDACTED_{kind}]", out)
            kinds.append(kind)
    return out, kinds


def redact_evidence(evidence: list[Evidence]) -> tuple[list[Evidence], list[str]]:
    """Redact PII in every evidence snippet. Returns (evidence, all_kinds_redacted)."""
    all_kinds: list[str] = []
    cleaned: list[Evidence] = []
    for e in evidence:
        red_title, k1 = redact_text(e.title)
        red_text, k2 = redact_text(e.text)
        kinds = k1 + k2
        for k in kinds:
            if k not in all_kinds:
                all_kinds.append(k)
        cleaned.append(
            e.model_copy(update={"title": red_title, "text": red_text, "redacted": bool(kinds)})
        )
    return cleaned, all_kinds
