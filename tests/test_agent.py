from guardrail_agent.agent import GuardrailAgent
from guardrail_agent.connectors import build_registry


def test_happy_path(fake_llm):
    trace = GuardrailAgent().run("What are the goals and blockers for Project X?")
    assert not trace.refused
    assert trace.answer is not None
    assert trace.answer.claims
    assert trace.answer.evidence
    assert trace.total_tokens > 0
    assert trace.latency_s >= 0
    # citations point at real evidence
    n = len(trace.answer.evidence)
    for claim in trace.answer.claims:
        assert all(1 <= c <= n for c in claim.citations)


def test_decompose_falls_back_to_single_subquestion(fake_llm):
    fake_llm.fail_stage = "decompose"
    trace = GuardrailAgent().run("Tell me about Project X goals")
    assert trace.decomposition is not None
    assert len(trace.decomposition.subquestions) == 1
    assert not trace.refused
    assert trace.answer.claims


def test_connector_failure_is_recorded_but_run_continues(fake_llm):
    agent = GuardrailAgent(connectors=build_registry(fail={"gmail"}))
    trace = agent.run("What are the Project X goals and tasks?")
    assert any("gmail" in e for e in trace.tool_errors)
    assert trace.answer is not None
    assert trace.answer.evidence  # notion/jira still answered


def test_synthesis_error_refuses(fake_llm):
    fake_llm.fail_stage = "synthesize"
    trace = GuardrailAgent().run("What are the Project X goals?")
    assert trace.refused
    assert "synthesis_error" in trace.refusal_reason


def test_no_matching_evidence_says_so(fake_llm):
    trace = GuardrailAgent().run("xylophone quantum tuba unicorn")
    assert not trace.refused
    assert trace.answer.claims
    assert trace.answer.claims[0].citations == []


def test_render_includes_citation_marks(fake_llm):
    trace = GuardrailAgent().run("What are the Project X blockers?")
    rendered = trace.answer.render()
    assert "[1]" in rendered
