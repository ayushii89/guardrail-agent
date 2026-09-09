"""LLM judge for answered eval cases.

Structural checks (outcome matches expectation, every claim cited) live in
run_eval.py. The judge only rules on answer *content*: does it address the
question, is it consistent with the expected facts, and - for missing-data
cases - does it correctly abstain instead of fabricating.
"""

from __future__ import annotations

from guardrail_agent.client import ModelResponseError, complete_json
from guardrail_agent.config import SETTINGS

_SYSTEM = """You grade an assistant's answer to a project-status question.

You are given: the question, the answer, a list of facts that should appear or be
consistent with the answer, and whether the case is an "abstain" case (the data does
not contain the answer, so the assistant should say it lacks evidence rather than guess).

Grade:
- correct: the answer addresses the question and does not contradict the expected facts.
  For abstain cases, "correct" means the answer clearly states the information is not
  available / not in the evidence and does NOT invent a specific answer.
- grounded: the answer stays within what such evidence could support (no obvious fabrication).

Return JSON: {"correct": bool, "grounded": bool, "reason": str (one sentence)}."""


def judge_answer(
    question: str,
    answer_text: str,
    must_include: list[str],
    abstain: bool,
) -> dict:
    user = (
        f"Question: {question}\n\n"
        f"Answer:\n{answer_text}\n\n"
        f"Expected facts: {must_include or '(none)'}\n"
        f"Abstain case: {abstain}"
    )
    try:
        data, _usage = complete_json(
            system=_SYSTEM, user=user, model=SETTINGS.judge_model, max_tokens=400
        )
        return {
            "correct": bool(data.get("correct", False)),
            "grounded": bool(data.get("grounded", False)),
            "reason": str(data.get("reason", "")),
        }
    except (ModelResponseError, KeyError, TypeError):
        return {"correct": False, "grounded": False, "reason": "judge failed to return a verdict"}
