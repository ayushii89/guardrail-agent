"""Tests for the Notion connector. No live API calls: the client is faked."""

import pytest

from guardrail_agent.connectors.base import ConnectorError
from guardrail_agent.connectors.notion import (
    NotionConnector,
    _blocks_to_text,
    _page_title,
)
from guardrail_agent.schema import Evidence

PAGE = {
    "id": "pg-1",
    "url": "https://notion.so/pg-1",
    "properties": {
        "Name": {
            "type": "title",
            "title": [{"plain_text": "Project X "}, {"plain_text": "Roadmap"}],
        }
    },
}

BLOCKS = [
    {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Goals"}]}},
    {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Expand to DE and FR."}]}},
    {"type": "image", "image": {}},
    {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "Ship beta"}]}},
]


class FakeNotion:
    def __init__(self, pages=None, boom=False):
        self._pages = pages if pages is not None else [PAGE]
        self._boom = boom
        self.blocks = self._Blocks()

    def search(self, **kwargs):
        if self._boom:
            raise RuntimeError("401 unauthorized")
        return {"results": self._pages}

    class _Blocks:
        class children:  # noqa: N801
            @staticmethod
            def list(**kwargs):
                return {"results": BLOCKS}

        def __init__(self):
            self.children = self.children()


def _connector(monkeypatch, client):
    c = NotionConnector(token="ntn_test")
    monkeypatch.setattr(c, "_get_client", lambda: client)
    return c


def test_page_title_joins_spans():
    assert _page_title(PAGE) == "Project X Roadmap"


def test_page_title_missing():
    assert _page_title({"properties": {}}) == "Untitled"


def test_blocks_to_text_keeps_only_text_blocks():
    text = _blocks_to_text(BLOCKS)
    assert text == "Goals Expand to DE and FR. Ship beta"


def test_falls_back_to_fixture_without_token(monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    c = NotionConnector()
    assert not c.is_live
    hits = c.search("project x goals", limit=2)
    assert hits and all(h.source == "notion" for h in hits)


def test_live_search_maps_pages_to_evidence(monkeypatch):
    c = _connector(monkeypatch, FakeNotion())
    assert c.is_live
    hits = c.search("roadmap", limit=3)
    assert len(hits) == 1
    e = hits[0]
    assert isinstance(e, Evidence)
    assert e.id == "pg-1"
    assert e.title == "Project X Roadmap"
    assert "Expand to DE and FR." in e.text
    assert e.url == "https://notion.so/pg-1"


def test_live_search_wraps_api_errors(monkeypatch):
    c = _connector(monkeypatch, FakeNotion(boom=True))
    with pytest.raises(ConnectorError):
        c.search("anything")


def test_simulated_failure(monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    with pytest.raises(ConnectorError):
        NotionConnector(fail=True).search("x")


def test_limit_is_respected(monkeypatch):
    pages = [dict(PAGE, id=f"pg-{i}") for i in range(5)]
    c = _connector(monkeypatch, FakeNotion(pages=pages))
    assert len(c.search("x", limit=2)) == 2
