"""Jira connector.

Real by default when ``JIRA_BASE_URL``, ``JIRA_EMAIL`` and ``JIRA_API_TOKEN`` are
set: it runs a JQL text search against the Jira Cloud REST API (v3) over the
stdlib, no SDK. Without the credentials it falls back to the local JSON fixture.

Setup for the real path:
  1. Create an API token at https://id.atlassian.com/manage-profile/security/api-tokens
  2. Set JIRA_BASE_URL (e.g. https://yoursite.atlassian.net), JIRA_EMAIL, JIRA_API_TOKEN
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from guardrail_agent.connectors.base import Connector, ConnectorError, FixtureConnector
from guardrail_agent.schema import Evidence

_TIMEOUT = 10
_MAX_CHARS = 1200


def _flatten_adf(node: object) -> str:
    """Collapse an Atlassian Document Format tree to plain text."""
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = [_flatten_adf(c) for c in node.get("content", [])]
        sep = "\n" if node.get("type") in {"paragraph", "heading"} else " "
        return sep.join(p for p in parts if p)
    if isinstance(node, list):
        return " ".join(_flatten_adf(c) for c in node)
    return ""


def _issue_to_evidence(issue: dict, base_url: str) -> Evidence:
    key = issue.get("key", "")
    fields = issue.get("fields", {})
    status = (fields.get("status") or {}).get("name", "")
    assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
    desc = _flatten_adf(fields.get("description")).strip()
    body = f"Status: {status}. Assignee: {assignee}. {desc}".strip()
    return Evidence(
        id=key,
        source="jira",
        title=f"{key}: {fields.get('summary', '')}".strip(": "),
        text=body[:_MAX_CHARS],
        url=f"{base_url.rstrip('/')}/browse/{key}",
    )


class JiraConnector(Connector):
    def __init__(self, fail: bool = False):
        self.name = "jira"
        self._fail = fail
        self._base = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        self._email = os.getenv("JIRA_EMAIL", "")
        self._token = os.getenv("JIRA_API_TOKEN", "")
        self._live = bool(self._base and self._email and self._token)
        self._fallback = None if self._live else FixtureConnector("jira", fail=fail)

    @property
    def is_live(self) -> bool:
        return self._fallback is None

    def _post(self, path: str, payload: dict) -> dict:
        creds = base64.b64encode(f"{self._email}:{self._token}".encode()).decode()
        req = urllib.request.Request(
            f"{self._base}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ConnectorError(f"jira: request failed ({e})") from e

    def search(self, query: str, limit: int = 3) -> list[Evidence]:
        if self._fail:
            raise ConnectorError("jira: simulated upstream failure")
        if self._fallback is not None:
            return self._fallback.search(query, limit)

        safe = query.replace('"', " ")
        data = self._post(
            "/rest/api/3/search/jql",
            {
                "jql": f'text ~ "{safe}" ORDER BY updated DESC',
                "maxResults": limit,
                "fields": ["summary", "status", "assignee", "description"],
            },
        )
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            raise ConnectorError("jira: unexpected response shape")
        return [_issue_to_evidence(i, self._base) for i in issues[:limit]]
