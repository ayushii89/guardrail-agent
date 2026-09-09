"""Shared test fixtures: a fake LLM so tests never hit the network."""

from __future__ import annotations

import re

import pytest

from guardrail_agent.client import ModelResponseError

_EVIDENCE_N = re.compile(r"\[(\d+)\]")


class FakeLLM:
    """Stub for ``complete_json``. Routes on the system prompt, records calls,
    and can be told to fail a given stage."""

    def __init__(self):
        self.calls: list[dict] = []
        self.fail_stage: str | None = None  # "decompose" | "synthesize"

    def complete_json(self, *, system: str, user: str, model: str, max_tokens: int = 1024):
        self.calls.append({"system": system, "user": user, "model": model})
        usage = (120, 40)

        if "sub-questions" in system:
            if self.fail_stage == "decompose":
                raise ModelResponseError("forced decompose failure")
            return {
                "subquestions": [
                    {"question": user, "connectors": ["gmail", "notion", "jira"]},
                ]
            }, usage

        if "numbered evidence" in system:
            if self.fail_stage == "synthesize":
                raise ModelResponseError("forced synthesize failure")
            nums = sorted({int(n) for n in _EVIDENCE_N.findall(user)})
            if not nums:
                return {"claims": [{"text": "No evidence available.", "citations": []}]}, usage
            return {
                "claims": [{"text": "Synthesized answer from evidence.", "citations": nums[:2]}]
            }, usage

        raise AssertionError(f"unexpected FakeLLM call with system={system[:60]!r}")


@pytest.fixture
def fake_llm(monkeypatch):
    stub = FakeLLM()
    monkeypatch.setattr("guardrail_agent.decompose.complete_json", stub.complete_json)
    monkeypatch.setattr("guardrail_agent.synthesize.complete_json", stub.complete_json)
    return stub
