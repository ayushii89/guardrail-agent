"""Connector registry and sub-question routing."""

from __future__ import annotations

from guardrail_agent.connectors.base import Connector
from guardrail_agent.connectors.gmail import GmailConnector
from guardrail_agent.connectors.jira import JiraConnector
from guardrail_agent.connectors.notion import NotionConnector

_CONNECTOR_CLASSES = {
    "gmail": GmailConnector,
    "notion": NotionConnector,
    "jira": JiraConnector,
}

_KEYWORDS = {
    "gmail": ("email", "mail", "message", "sent", "reply", "thread", "inbox"),
    "notion": ("doc", "note", "page", "spec", "goal", "roadmap", "plan", "requirement"),
    "jira": ("ticket", "issue", "bug", "blocker", "sprint", "story", "task", "deadline", "status"),
}


def build_registry(fail: set[str] | None = None) -> dict[str, Connector]:
    fail = fail or set()
    return {name: cls(fail=name in fail) for name, cls in _CONNECTOR_CLASSES.items()}


def route(question: str, hinted: list[str] | None = None) -> list[str]:
    """Pick connectors for a sub-question. Falls back to all three."""
    if hinted:
        valid = [h for h in hinted if h in _CONNECTOR_CLASSES]
        if valid:
            return valid
    q = question.lower()
    picked = [name for name, kws in _KEYWORDS.items() if any(k in q for k in kws)]
    return picked or list(_CONNECTOR_CLASSES)
