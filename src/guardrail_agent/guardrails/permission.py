"""Permission layer: this agent is read-only.

If the user asks it to *take an action* in a connected system (send an email,
close a ticket, edit a doc, delete something), we do not do it. We stop and
report that confirmation / a human is required. Deterministic by design.
"""

from __future__ import annotations

import re

from guardrail_agent.schema import GuardrailResult, Stage

_ACTION_VERBS = (
    "send",
    "email",
    "reply",
    "forward",
    "delete",
    "remove",
    "close",
    "resolve",
    "reopen",
    "assign",
    "create",
    "update",
    "edit",
    "change",
    "post",
    "comment",
    "schedule",
    "cancel",
    "approve",
    "merge",
    "deploy",
    "pay",
    "transfer",
)

_READ_FRAMING = re.compile(
    r"^\s*(what|which|who|when|where|why|how|list|show|summar|tell me|give me"
    r"|find|is |are |do |does |describe|explain)",
    re.I,
)


def check_permission(question: str) -> GuardrailResult:
    q = question.lower()
    verbs = sorted({v for v in _ACTION_VERBS if re.search(rf"\b{v}\b", q)})

    # Read-style phrasing overrides an incidental verb ("what emails were sent?").
    if verbs and not _READ_FRAMING.match(question):
        return GuardrailResult(
            stage=Stage.PERMISSION,
            allowed=False,
            violated_policies=["risky_action"],
            severity="medium",
            rationale=(
                f"request appears to ask the agent to take an action ({', '.join(verbs)}); "
                "this agent is read-only and requires human confirmation for actions"
            ),
        )

    return GuardrailResult(stage=Stage.PERMISSION, allowed=True)
