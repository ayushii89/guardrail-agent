"""Agent orchestrator.

Guardrailed pipeline:

    input guardrail -> permission -> decompose -> retrieve -> evidence scan
      -> PII redaction -> synthesize -> citation validation -> output validation
"""

from __future__ import annotations

import time

from guardrail_agent.client import ModelResponseError
from guardrail_agent.connectors import build_registry, route
from guardrail_agent.connectors.base import Connector, ConnectorError
from guardrail_agent.decompose import decompose
from guardrail_agent.guardrails import (
    check_input,
    check_permission,
    redact_evidence,
    scan_evidence,
    validate_citations,
    validate_output,
)
from guardrail_agent.schema import AgentTrace, Evidence, GuardrailResult, Stage
from guardrail_agent.synthesize import synthesize


class GuardrailAgent:
    def __init__(self, connectors: dict[str, Connector] | None = None, per_source_limit: int = 3):
        self.connectors = connectors if connectors is not None else build_registry()
        self.per_source_limit = per_source_limit

    def _retrieve(self, trace: AgentTrace) -> list[Evidence]:
        seen: dict[str, Evidence] = {}
        assert trace.decomposition is not None
        for sub in trace.decomposition.subquestions:
            for name in route(sub.question, sub.connectors):
                conn = self.connectors.get(name)
                if conn is None:
                    continue
                try:
                    hits = conn.search(sub.question, limit=self.per_source_limit)
                except ConnectorError as e:
                    trace.tool_errors.append(str(e))
                    continue
                for h in hits:
                    seen.setdefault(h.id, h)
        return list(seen.values())

    def run(self, question: str) -> AgentTrace:
        started = time.perf_counter()
        trace = AgentTrace(question=question)

        def finish() -> AgentTrace:
            trace.latency_s = round(time.perf_counter() - started, 3)
            return trace

        def add_tokens(usage: tuple[int, int]) -> None:
            trace.input_tokens += usage[0]
            trace.output_tokens += usage[1]

        # 1. input guardrail
        g_in, usage = check_input(question)
        trace.guardrails.append(g_in)
        add_tokens(usage)
        if g_in.blocked:
            trace.refused = True
            trace.refusal_reason = f"input_guardrail: {g_in.rationale}"
            return finish()

        # 2. permission layer (read-only agent)
        g_perm = check_permission(question)
        trace.guardrails.append(g_perm)
        if g_perm.blocked:
            trace.needs_confirmation = True
            trace.refusal_reason = g_perm.rationale
            return finish()

        # 3. decompose
        decomp, usage = decompose(question)
        trace.decomposition = decomp
        add_tokens(usage)

        # 4. retrieve
        evidence = self._retrieve(trace)

        # 5. evidence scan: strip instruction-like text from untrusted documents
        evidence, g_scan = scan_evidence(evidence)
        trace.guardrails.append(g_scan)

        # 6. PII redaction (before evidence reaches the synthesis model)
        evidence, kinds = redact_evidence(evidence)
        trace.guardrails.append(
            GuardrailResult(
                stage=Stage.PII_REDACTION,
                allowed=True,
                violated_policies=["pii_present"] if kinds else [],
                severity="low" if kinds else "none",
                rationale=f"redacted {kinds}" if kinds else "no PII found",
            )
        )

        # 7. synthesize
        try:
            answer, usage = synthesize(question, evidence)
            add_tokens(usage)
        except ModelResponseError as e:
            trace.refused = True
            trace.refusal_reason = f"synthesis_error: {e}"
            return finish()

        # 8. citation validation
        answer, g_cite, usage = validate_citations(answer)
        trace.guardrails.append(g_cite)
        add_tokens(usage)

        # 9. output validation
        answer, g_out = validate_output(answer)
        trace.guardrails.append(g_out)
        trace.answer = answer
        if g_out.blocked:
            trace.refused = True
            trace.refusal_reason = f"output_validation: {g_out.rationale}"

        return finish()
