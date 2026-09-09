"""Tests for the Jira connector. No live calls: _post is faked."""

import pytest

from guardrail_agent.connectors.base import ConnectorError
from guardrail_agent.connectors.jira import JiraConnector, _flatten_adf, _issue_to_evidence

ADF = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Staging is down."}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Blocks QA."}]},
    ],
}

ISSUE = {
    "key": "PX-102",
    "fields": {
        "summary": "Staging environment down",
        "status": {"name": "Open"},
        "assignee": {"displayName": "Chen"},
        "description": ADF,
    },
}


@pytest.fixture
def live(monkeypatch):
    for k, v in {
        "JIRA_BASE_URL": "https://acme.atlassian.net",
        "JIRA_EMAIL": "a@b.com",
        "JIRA_API_TOKEN": "tok",
    }.items():
        monkeypatch.setenv(k, v)
    return JiraConnector()


def test_flatten_adf():
    assert _flatten_adf(ADF) == "Staging is down. Blocks QA."


def test_issue_to_evidence():
    e = _issue_to_evidence(ISSUE, "https://acme.atlassian.net")
    assert e.id == "PX-102"
    assert e.title == "PX-102: Staging environment down"
    assert "Status: Open" in e.text and "Chen" in e.text and "Staging is down." in e.text
    assert e.url == "https://acme.atlassian.net/browse/PX-102"


def test_fallback_without_credentials(monkeypatch):
    for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    c = JiraConnector()
    assert not c.is_live
    assert c.search("staging blocker", limit=2)


def test_live_search_maps_issues(monkeypatch, live):
    assert live.is_live
    monkeypatch.setattr(live, "_post", lambda *a, **k: {"issues": [ISSUE]})
    hits = live.search("staging", limit=3)
    assert len(hits) == 1 and hits[0].id == "PX-102"


def test_live_search_wraps_errors(monkeypatch, live):
    def boom(*a, **k):
        raise ConnectorError("jira: request failed (500)")

    monkeypatch.setattr(live, "_post", boom)
    with pytest.raises(ConnectorError):
        live.search("x")


def test_simulated_failure(monkeypatch):
    for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ConnectorError):
        JiraConnector(fail=True).search("x")
