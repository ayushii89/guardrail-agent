"""Mock Gmail connector.

A real implementation would swap ``FixtureConnector.search`` for a call to the
Gmail API (``users.messages.list`` + ``get``) and map the response into
``Evidence``. The rest of the pipeline is unaffected.
"""

from __future__ import annotations

from guardrail_agent.connectors.base import FixtureConnector


class GmailConnector(FixtureConnector):
    def __init__(self, fail: bool = False):
        super().__init__("gmail", fail=fail)
