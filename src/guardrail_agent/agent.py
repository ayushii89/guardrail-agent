"""Agent orchestrator.

Day 2 pipeline (guardrails are layered in on Day 3):

    decompose -> retrieve per sub-question -> dedupe -> synthesize
"""

from __future__ import annotations

import time

from guardrail_agent.client import ModelResponseError
from guardrail_agent.connectors import build_registry, route
from guardrail_agent.connectors.base import Connector, ConnectorError
from guardrail_agent.decompose import decompose
from guardrail_agent.schema import AgentTrace, Evidence
from guardrail_agent.synthesize import synthesize


class GuardrailAgent:
    def __init__(self, connectors: dict[str, Connector] | None = None, per_source_limit: int = 3):
        self.connectors = connectors or build_registry()
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

        decomp, usage = decompose(question)
        trace.decomposition = decomp
        trace.input_tokens += usage[0]
        trace.output_tokens += usage[1]

        evidence = self._retrieve(trace)

        try:
            answer, usage = synthesize(question, evidence)
            trace.answer = answer
            trace.input_tokens += usage[0]
            trace.output_tokens += usage[1]
        except ModelResponseError as e:
            trace.refused = True
            trace.refusal_reason = f"synthesis_error: {e}"

        trace.latency_s = round(time.perf_counter() - started, 3)
        return trace
