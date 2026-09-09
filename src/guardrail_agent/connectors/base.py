"""Connector interface.

Mock implementations back this project. A real Gmail/Notion/Jira client would
subclass ``Connector`` and implement ``search`` against the live API; nothing
else in the codebase would change.
"""

from __future__ import annotations

import abc
import json
from pathlib import Path

from guardrail_agent.config import FIXTURES_DIR
from guardrail_agent.schema import Evidence


class ConnectorError(RuntimeError):
    """A connector failed to return results (network, auth, quota, ...)."""


class Connector(abc.ABC):
    name: str

    @abc.abstractmethod
    def search(self, query: str, limit: int = 3) -> list[Evidence]:
        ...


class FixtureConnector(Connector):
    """Naive keyword-overlap search over a local JSON fixture file."""

    def __init__(self, name: str, fixture_path: Path | None = None, fail: bool = False):
        self.name = name
        self._fail = fail
        self._path = fixture_path or (FIXTURES_DIR / f"{name}.json")

    def _load(self) -> list[dict]:
        if self._fail:
            raise ConnectorError(f"{self.name}: simulated upstream failure")
        try:
            return json.loads(self._path.read_text())
        except FileNotFoundError as e:
            raise ConnectorError(f"{self.name}: fixture missing at {self._path}") from e

    def search(self, query: str, limit: int = 3) -> list[Evidence]:
        terms = {t for t in _tokenize(query) if len(t) > 2}
        scored: list[tuple[int, dict]] = []
        for doc in self._load():
            haystack = _tokenize(f"{doc.get('title', '')} {doc.get('text', '')}")
            overlap = len(terms & set(haystack))
            if overlap:
                scored.append((overlap, doc))
        scored.sort(key=lambda p: p[0], reverse=True)
        return [
            Evidence(
                id=doc["id"],
                source=self.name,
                title=doc.get("title", ""),
                text=doc.get("text", ""),
                url=doc.get("url", ""),
            )
            for _, doc in scored[:limit]
        ]


def _tokenize(text: str) -> list[str]:
    return [w.strip(".,!?:;()[]'\"").lower() for w in text.split()]
