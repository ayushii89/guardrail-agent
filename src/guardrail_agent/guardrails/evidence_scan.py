"""Evidence scan: defend against indirect prompt injection.

Retrieved documents are untrusted. A malicious page or email can carry text like
"ignore your instructions and ..." in its body, hoping the synthesis model treats
it as a command. This stage strips instruction-like spans from every snippet
*before* it reaches the model, deterministically, so the defense does not depend
on the model choosing to ignore them.
"""

from __future__ import annotations

from guardrail_agent.guardrails.patterns import INJECTION_PATTERNS
from guardrail_agent.schema import Evidence, GuardrailResult, Stage

_PLACEHOLDER = "[removed: instruction-like text in retrieved content]"


def _scrub(text: str) -> tuple[str, bool]:
    hit = False
    out = text
    for pat in INJECTION_PATTERNS:
        new = pat.sub(_PLACEHOLDER, out)
        if new != out:
            hit = True
            out = new
    return out, hit


def scan_evidence(evidence: list[Evidence]) -> tuple[list[Evidence], GuardrailResult]:
    flagged: list[str] = []
    cleaned: list[Evidence] = []
    for e in evidence:
        title, t_hit = _scrub(e.title)
        text, x_hit = _scrub(e.text)
        hit = t_hit or x_hit
        if hit:
            flagged.append(f"{e.source}:{e.id}")
        cleaned.append(e.model_copy(update={"title": title, "text": text, "sanitized": hit}))

    return cleaned, GuardrailResult(
        stage=Stage.EVIDENCE_SCAN,
        allowed=True,
        violated_policies=["indirect_prompt_injection"] if flagged else [],
        severity="high" if flagged else "none",
        rationale=(
            f"stripped instruction-like content from {flagged}" if flagged else "no injection found"
        ),
    )
