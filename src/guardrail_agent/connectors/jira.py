"""Mock Jira connector. See gmail.py for how a real client would slot in."""

from __future__ import annotations

from guardrail_agent.connectors.base import FixtureConnector


class JiraConnector(FixtureConnector):
    def __init__(self, fail: bool = False):
        super().__init__("jira", fail=fail)
