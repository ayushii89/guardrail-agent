import pytest

from guardrail_agent.connectors import build_registry, route
from guardrail_agent.connectors.base import ConnectorError
from guardrail_agent.schema import Evidence


def test_registry_has_all_three():
    reg = build_registry()
    assert set(reg) == {"gmail", "notion", "jira"}


def test_search_returns_relevant_evidence():
    reg = build_registry()
    hits = reg["jira"].search("staging environment blocker", limit=3)
    assert hits
    assert all(isinstance(h, Evidence) for h in hits)
    assert hits[0].source == "jira"
    assert "PX-102" == hits[0].id  # best keyword overlap


def test_search_limit_is_respected():
    reg = build_registry()
    hits = reg["notion"].search("project x goals tasks deadlines", limit=2)
    assert len(hits) <= 2


def test_search_no_match_returns_empty():
    reg = build_registry()
    assert reg["gmail"].search("xylophone quantum tuba") == []


def test_simulated_connector_failure_raises():
    reg = build_registry(fail={"gmail"})
    with pytest.raises(ConnectorError):
        reg["gmail"].search("project x goals")
    # other connectors still work
    assert reg["notion"].search("project x goals")


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What emails did the sponsor send?", ["gmail"]),
        ("Which Jira tickets are blockers?", ["jira"]),
        ("What does the Notion roadmap doc say?", ["notion"]),
        ("Tell me everything about Project X", ["gmail", "notion", "jira"]),
    ],
)
def test_routing(question, expected):
    assert route(question) == expected


def test_routing_respects_valid_hints():
    assert route("anything", hinted=["jira", "bogus"]) == ["jira"]
