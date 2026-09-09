"""Pydantic models shared across the agent, guardrails, and evals."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Stage(str, Enum):
    INPUT_GUARDRAIL = "input_guardrail"
    DECOMPOSE = "decompose"
    RETRIEVE = "retrieve"
    PII_REDACTION = "pii_redaction"
    SYNTHESIZE = "synthesize"
    CITATION_VALIDATION = "citation_validation"
    OUTPUT_VALIDATION = "output_validation"
    PERMISSION = "permission"


class GuardrailResult(BaseModel):
    """Outcome of a single guardrail check."""

    stage: Stage
    allowed: bool
    violated_policies: list[str] = Field(default_factory=list)
    severity: str = "none"  # none | low | medium | high
    rationale: str = ""

    @property
    def blocked(self) -> bool:
        return not self.allowed


class Evidence(BaseModel):
    """A single retrieved snippet, already PII-redacted before synthesis."""

    id: str
    source: str  # gmail | notion | jira
    title: str
    text: str
    url: str = ""
    redacted: bool = False


class SubQuestion(BaseModel):
    question: str
    connectors: list[str] = Field(default_factory=list)


class Decomposition(BaseModel):
    subquestions: list[SubQuestion]


class Claim(BaseModel):
    text: str
    citations: list[int] = Field(default_factory=list)
    kind: str = "assertion"  # "assertion" | "abstention"

    @property
    def is_abstention(self) -> bool:
        return self.kind == "abstention"


class AgentAnswer(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    def render(self) -> str:
        lines = []
        for c in self.claims:
            marks = "".join(f"[{n}]" for n in c.citations)
            lines.append(f"{c.text} {marks}".strip())
        return "\n".join(lines)


class AgentTrace(BaseModel):
    """Everything that happened during one run, for tests, evals, and audit."""

    question: str
    refused: bool = False
    refusal_reason: str = ""
    needs_confirmation: bool = False
    tool_errors: list[str] = Field(default_factory=list)
    guardrails: list[GuardrailResult] = Field(default_factory=list)
    decomposition: Decomposition | None = None
    answer: AgentAnswer | None = None
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def final_text(self) -> str:
        if self.refused:
            return f"REFUSED: {self.refusal_reason}"
        if self.needs_confirmation:
            return "CONFIRMATION REQUIRED before proceeding."
        return self.answer.render() if self.answer else ""
