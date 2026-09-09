"""Citation validation: every claim must be entailed by the evidence it cites.

Claims that fail (no citation, or cited evidence does not support them) are
dropped from the answer and recorded on the guardrail result.
"""

from __future__ import annotations

from guardrail_agent.client import ModelResponseError, complete_json
from guardrail_agent.config import SETTINGS
from guardrail_agent.schema import AgentAnswer, GuardrailResult, Stage

_SYSTEM = """You verify citations. For each claim you are given its text and the full text \
of every evidence snippet it cites. Decide whether the cited evidence actually supports \
the claim (entailment, not just topical overlap).

Return JSON: {"verdicts": [{"index": int, "supported": bool, "reason": str}, ...]} with one \
entry per claim, using the claim's 0-based index."""


def validate_citations(
    answer: AgentAnswer,
) -> tuple[AgentAnswer, GuardrailResult, tuple[int, int]]:
    if not answer.claims:
        return answer, GuardrailResult(stage=Stage.CITATION_VALIDATION, allowed=True), (0, 0)

    ev_by_n = {i: e for i, e in enumerate(answer.evidence, start=1)}

    # An explicit "no evidence" claim with no citations is allowed through.
    def _is_no_evidence(text: str) -> bool:
        t = text.lower()
        return ("no evidence" in t) or ("does not" in t and "answer" in t)

    payload_lines = []
    for idx, claim in enumerate(answer.claims):
        cited = "\n".join(
            f"    [{n}] {ev_by_n[n].text}" for n in claim.citations if n in ev_by_n
        )
        payload_lines.append(
            f"[claim {idx}] {claim.text}\n  cited evidence:\n{cited or '    (none)'}"
        )
    user = "\n\n".join(payload_lines)

    usage = (0, 0)
    try:
        data, usage = complete_json(
            system=_SYSTEM, user=user, model=SETTINGS.judge_model, max_tokens=1200
        )
        verdicts = {int(v["index"]): bool(v["supported"]) for v in data.get("verdicts", [])}
    except (ModelResponseError, KeyError, TypeError, ValueError):
        # Fail closed: keep only claims whose citations exist.
        verdicts = {}

    kept, dropped = [], []
    for idx, claim in enumerate(answer.claims):
        has_valid_citation = any(n in ev_by_n for n in claim.citations)
        supported = verdicts.get(idx, has_valid_citation)
        no_evidence_claim = not claim.citations and _is_no_evidence(claim.text)
        if (has_valid_citation and supported) or no_evidence_claim:
            kept.append(claim)
        else:
            dropped.append(claim.text)

    new_answer = answer.model_copy(update={"claims": kept})
    rationale = (
        f"dropped {len(dropped)} unsupported claim(s): {dropped}"
        if dropped
        else "all claims supported"
    )
    result = GuardrailResult(
        stage=Stage.CITATION_VALIDATION,
        allowed=bool(kept),
        violated_policies=["unsupported_claim"] if dropped else [],
        severity="medium" if dropped else "none",
        rationale=rationale,
    )
    return new_answer, result, usage
