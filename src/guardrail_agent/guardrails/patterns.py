"""Shared regex patterns for instruction-injection detection.

Used both by the input guardrail (screening the user's message) and the evidence
scan (screening retrieved documents for indirect prompt injection).
"""

from __future__ import annotations

import re

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"ignore (?:all |any |the )?(?:previous|prior|above) (?:instructions|prompts)", re.I
    ),
    re.compile(r"disregard (?:the |your |all )?(?:system prompt|instructions|rules)", re.I),
    re.compile(r"you are now (?:a |an )?(?:dan|developer mode|unrestricted)", re.I),
    re.compile(
        r"(?:reveal|print|repeat|show|output) (?:your |the )?(?:system prompt|instructions)", re.I
    ),
    re.compile(r"pretend (?:you are|to be) (?:not |un)", re.I),
    re.compile(r"new instructions?:", re.I),
    re.compile(r"</?(?:system|instructions?)>", re.I),
    re.compile(r"\bassistant\s*:\s*(?:sure|okay|here)", re.I),
]


def find_injection(text: str) -> re.Pattern[str] | None:
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            return pat
    return None
