"""The session helper writes a folder outside the repository and nowhere else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smr.review_mcp._session import prepare, session_main


def _repo() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "compose.yaml").is_file():
            return parent
    msg = "repository root"
    raise RuntimeError(msg)


def test_the_command_writes_the_folder(tmp_path: Path) -> None:
    """`smr-review-session <folder>` is the same writer."""
    destination = tmp_path / "out"
    session_main([str(destination)])
    assert (destination / ".mcp.json").is_file()


def test_a_folder_outside_the_repository_is_filled_in(tmp_path: Path) -> None:
    """CLAUDE.md, the settings and .mcp.json land outside, with the compose path."""
    destination = tmp_path / "seminarist-review"
    prepare(destination)
    root = _repo()
    assert (destination / "CLAUDE.md").read_text(encoding="utf-8") == (
        root / "apps" / "review_mcp" / "session" / "CLAUDE.md"
    ).read_text(encoding="utf-8")
    settings = (destination / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "mcp__seminarist-review__*" in settings
    written = json.loads((destination / ".mcp.json").read_text(encoding="utf-8"))
    args = written["mcpServers"]["seminarist-review"]["args"]
    compose = (root / "compose.yaml").resolve().as_posix()
    assert compose in args
    assert "/ABS/PATH/compose.yaml" not in args


def test_a_folder_inside_the_repository_is_refused(tmp_path: Path) -> None:
    """Student pages must not be created in the checkout."""
    del tmp_path
    inside = _repo() / "apps" / "review_mcp" / "tests" / "unit" / "not-a-session"
    with pytest.raises(SystemExit):
        prepare(inside)
    assert not inside.exists()
