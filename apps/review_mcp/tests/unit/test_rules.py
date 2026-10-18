"""The server and the session template carry the same grading rules."""

from __future__ import annotations

from pathlib import Path

from smr.review_mcp._rules import RULES

_SESSION = Path(__file__).resolve().parents[2] / "session" / "CLAUDE.md"


def test_the_session_template_matches_the_server_rules() -> None:
    """CLAUDE.md is the instructions the server also sends."""
    assert _SESSION.read_text(encoding="utf-8") == RULES
