"""Notion connector.

Real by default when ``NOTION_API_KEY`` is set: it queries the Notion search API
and reads page content. Without a token it transparently falls back to the local
JSON fixture, so tests, evals, and other users are unaffected.

Setup for the real path:
  1. Create an internal integration at https://www.notion.so/my-integrations
  2. Copy its token into ``NOTION_API_KEY``
  3. Share the pages / databases you want searchable with that integration
  4. ``pip install -e ".[notion]"``
"""

from __future__ import annotations

import os

from guardrail_agent.connectors.base import Connector, ConnectorError, FixtureConnector
from guardrail_agent.schema import Evidence

_TEXT_BLOCKS = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "quote",
    "callout",
}
_MAX_BLOCKS = 20
_MAX_CHARS = 1400


def _rich_text(block: dict) -> str:
    body = block.get(block.get("type", ""), {})
    spans = body.get("rich_text", []) if isinstance(body, dict) else []
    return "".join(s.get("plain_text", "") for s in spans)


def _page_title(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(s.get("plain_text", "") for s in prop.get("title", [])) or "Untitled"
    return "Untitled"


def _blocks_to_text(blocks: list[dict]) -> str:
    parts = []
    for b in blocks[:_MAX_BLOCKS]:
        if b.get("type") in _TEXT_BLOCKS:
            t = _rich_text(b).strip()
            if t:
                parts.append(t)
    return " ".join(parts)[:_MAX_CHARS]


class NotionConnector(Connector):
    def __init__(self, fail: bool = False, token: str | None = None):
        self.name = "notion"
        self._fail = fail
        self._token = token or os.getenv("NOTION_API_KEY")
        self._fallback = None if self._token else FixtureConnector("notion", fail=fail)
        self._client = None

    @property
    def is_live(self) -> bool:
        return self._fallback is None

    def _get_client(self):
        if self._client is None:
            try:
                from notion_client import Client
            except ImportError as e:
                raise ConnectorError(
                    "notion: NOTION_API_KEY is set but notion-client is not installed "
                    '(pip install -e ".[notion]")'
                ) from e
            self._client = Client(auth=self._token)
        return self._client

    def search(self, query: str, limit: int = 3) -> list[Evidence]:
        if self._fail:
            raise ConnectorError("notion: simulated upstream failure")
        if self._fallback is not None:
            return self._fallback.search(query, limit)

        client = self._get_client()
        try:
            resp = client.search(
                query=query,
                filter={"property": "object", "value": "page"},
                page_size=limit,
            )
        except Exception as e:  # notion_client.APIResponseError and transport errors
            raise ConnectorError(f"notion: search failed ({e})") from e

        out: list[Evidence] = []
        for page in resp.get("results", [])[:limit]:
            page_id = page.get("id", "")
            try:
                children = client.blocks.children.list(block_id=page_id, page_size=_MAX_BLOCKS)
                text = _blocks_to_text(children.get("results", []))
            except Exception:
                text = ""
            out.append(
                Evidence(
                    id=page_id,
                    source="notion",
                    title=_page_title(page),
                    text=text or _page_title(page),
                    url=page.get("url", ""),
                )
            )
        return out
