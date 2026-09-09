"""Output validation: the last gate before the answer is returned.

Checks, in order:
  1. non-empty  - at least one claim survived
  2. grounded   - every claim carries a citation (except an explicit "no evidence" claim)
  3. pii-clean  - no PII in the rendered answer; if any slipped through, redact it
"""

from __future__ import annotations

from guardrail_agent.guardrails.pii import redact_text, scan_pii
from guardrail_agent.schema import AgentAnswer, GuardrailResult, Stage


def validate_output(answer: AgentAnswer) -> tuple[AgentAnswer, GuardrailResult]:
    policies: list[str] = []
    severity = "none"

    if not answer.claims:
        return answer, GuardrailResult(
            stage=Stage.OUTPUT_VALIDATION,
            allowed=False,
            violated_policies=["empty_answer"],
            severity="high",
            rationale="no claims survived validation",
        )

    ungrounded = [
        c.text
        for c in answer.claims
        if not c.citations and "no evidence" not in c.text.lower()
    ]
    if ungrounded:
        policies.append("ungrounded_claim")
        severity = "high"

    rendered = answer.render()
    leaked = scan_pii(rendered)
    new_answer = answer
    if leaked:
        policies.append("pii_leak")
        severity = "high"
        new_claims = []
        for c in answer.claims:
            red, _ = redact_text(c.text)
            new_claims.append(c.model_copy(update={"text": red}))
        new_answer = answer.model_copy(update={"claims": new_claims})

    allowed = "ungrounded_claim" not in policies
    return new_answer, GuardrailResult(
        stage=Stage.OUTPUT_VALIDATION,
        allowed=allowed,
        violated_policies=policies,
        severity=severity,
        rationale=(
            f"ungrounded: {ungrounded}; " if ungrounded else ""
        ) + (f"redacted leaked PII: {leaked}" if leaked else ("ok" if allowed else "")),
    )
