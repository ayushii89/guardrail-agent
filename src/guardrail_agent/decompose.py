"""LLM query decomposition: split a question into retrievable sub-questions."""

from __future__ import annotations

from guardrail_agent.client import ModelResponseError, complete_json
from guardrail_agent.config import SETTINGS
from guardrail_agent.schema import Decomposition, SubQuestion

_SYSTEM = """You break a user's question about internal project status into a short list \
of focused sub-questions that can each be answered by searching a knowledge source.

Available sources: "gmail" (emails), "notion" (docs, specs, roadmaps), "jira" (tickets, \
bugs, blockers, status). For each sub-question, list the 1-3 sources most likely to hold \
the answer.

Return JSON: {"subquestions": [{"question": str, "connectors": [str, ...]}, ...]}.
Do not invent facts; only restructure the question.
Produce at most """ + str(SETTINGS.max_subquestions) + " sub-questions."


def decompose(question: str) -> tuple[Decomposition, tuple[int, int]]:
    """Return (decomposition, (input_tokens, output_tokens))."""
    usage = (0, 0)
    try:
        data, usage = complete_json(
            system=_SYSTEM,
            user=question,
            model=SETTINGS.agent_model,
            max_tokens=800,
        )
        raw = data.get("subquestions") or []
        subs = [
            SubQuestion(
                question=str(item["question"]),
                connectors=[str(c) for c in item.get("connectors", [])],
            )
            for item in raw
            if isinstance(item, dict) and item.get("question")
        ]
    except (ModelResponseError, KeyError, TypeError):
        subs = []

    if not subs:
        subs = [SubQuestion(question=question, connectors=[])]
    return Decomposition(subquestions=subs[: SETTINGS.max_subquestions]), usage
