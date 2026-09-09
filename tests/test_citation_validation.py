from guardrail_agent.guardrails.citation_validation import validate_citations
from guardrail_agent.schema import AgentAnswer, Claim, Evidence

EV = [
    Evidence(id="1", source="notion", title="Goals", text="Project X expands into DE and FR."),
    Evidence(id="2", source="jira", title="PX-102", text="Staging is down. Blocker."),
]


def _answer(claims):
    return AgentAnswer(claims=claims, evidence=EV)


def test_drops_claim_with_no_citation(monkeypatch):
    monkeypatch.setattr(
        "guardrail_agent.guardrails.citation_validation.complete_json",
        lambda **_: ({"verdicts": []}, (0, 0)),
    )
    ans = _answer(
        [
            Claim(text="Project X expands into DE and FR.", citations=[1]),
            Claim(text="Project X will acquire a competitor.", citations=[]),
        ]
    )
    new_ans, res, _ = validate_citations(ans)
    assert len(new_ans.claims) == 1
    assert "unsupported_claim" in res.violated_policies


def test_drops_claim_the_judge_marks_unsupported(monkeypatch):
    monkeypatch.setattr(
        "guardrail_agent.guardrails.citation_validation.complete_json",
        lambda **_: (
            {"verdicts": [{"index": 0, "supported": True}, {"index": 1, "supported": False}]},
            (0, 0),
        ),
    )
    ans = _answer(
        [
            Claim(text="Project X expands into DE and FR.", citations=[1]),
            Claim(text="Staging is fully operational.", citations=[2]),
        ]
    )
    new_ans, res, _ = validate_citations(ans)
    assert [c.text for c in new_ans.claims] == ["Project X expands into DE and FR."]
    assert res.severity == "medium"


def test_keeps_explicit_no_evidence_claim(monkeypatch):
    monkeypatch.setattr(
        "guardrail_agent.guardrails.citation_validation.complete_json",
        lambda **_: ({"verdicts": []}, (0, 0)),
    )
    ans = _answer(
        [Claim(text="The evidence does not answer this.", citations=[], kind="abstention")]
    )
    new_ans, res, _ = validate_citations(ans)
    assert len(new_ans.claims) == 1
    assert res.allowed


def test_fails_closed_when_judge_errors(monkeypatch):
    from guardrail_agent.client import ModelResponseError

    def boom(**_):
        raise ModelResponseError("judge down")

    monkeypatch.setattr("guardrail_agent.guardrails.citation_validation.complete_json", boom)
    ans = _answer(
        [
            Claim(text="Grounded claim.", citations=[1]),
            Claim(text="Hallucinated claim.", citations=[]),
        ]
    )
    new_ans, _res, _ = validate_citations(ans)
    # fail-closed keeps only claims whose citations exist
    assert [c.text for c in new_ans.claims] == ["Grounded claim."]
