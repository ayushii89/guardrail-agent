"""Runtime configuration, driven by environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"


@dataclass(frozen=True)
class Settings:
    agent_model: str = os.getenv("GUARDRAIL_AGENT_MODEL", "claude-opus-5")
    guard_model: str = os.getenv("GUARDRAIL_GUARD_MODEL", "claude-sonnet-5")
    judge_model: str = os.getenv("GUARDRAIL_JUDGE_MODEL", "claude-sonnet-5")

    # Domain the agent is allowed to answer about. Anything else is refused by
    # the input guardrail as out of scope.
    domain: str = (
        "internal project status: goals, tasks, deadlines, blockers, and owners "
        "for work tracked in the connected Gmail, Notion, and Jira workspaces"
    )

    max_subquestions: int = 6

    def require_api_key(self) -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        return key


SETTINGS = Settings()
