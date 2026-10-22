"""Create the grading-agent folder outside the repository."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

_USAGE = "usage: smr-review-session <folder>\n"


def session_main(argv: list[str] | None = None) -> None:
    """Write a session folder for `smr-review-session <folder>`.

    Args:
        argv: list[str] | None - Arguments, without the program name. The process
            arguments when omitted.

    Raises:
        SystemExit: If the arguments are missing or the folder is refused.

    """
    raw = sys.argv[1:] if argv is None else argv
    if raw in (["-h"], ["--help"]):
        _ = sys.stdout.write(_USAGE)
        raise SystemExit(0)
    if len(raw) != 1:
        _ = sys.stderr.write(_USAGE)
        raise SystemExit(1)
    prepare(Path(raw[0]))


def prepare(destination: Path) -> None:
    """Write CLAUDE.md, the Claude settings and .mcp.json.

    A path inside the repository, an occupied path, or a checkout without the
    template stops the command before anything is written.

    Args:
        destination: Path - The new folder.

    """
    target = destination.expanduser().resolve()
    root = _repo_root()
    if target == root or target.is_relative_to(root):
        _refuse(f"{target} is inside the repository")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        _refuse(f"{target} already exists")
    template = root / "apps" / "review_mcp" / "session"
    compose = root / "compose.yaml"
    if not compose.is_file() or not (template / "CLAUDE.md").is_file():
        _refuse(f"session template is missing in {root}")
    target.mkdir(parents=True, exist_ok=True)
    _ = (target / "CLAUDE.md").write_text(
        (template / "CLAUDE.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    claude = target / ".claude"
    claude.mkdir()
    _ = (claude / "settings.json").write_text(
        (template / ".claude" / "settings.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    example = (template / "mcp.json.example").read_text(encoding="utf-8")
    filled = example.replace("/ABS/PATH/compose.yaml", compose.resolve().as_posix())
    _ = (target / ".mcp.json").write_text(filled, encoding="utf-8")


def _repo_root() -> Path:
    """Find the checkout that contains this command and compose.yaml.

    Returns:
        Path - The repository root. A checkout that has neither file stops the command.

    """
    starts = (Path(__file__).resolve(), Path.cwd().resolve())
    for start in starts:
        for parent in (start, *start.parents):
            compose = (parent / "compose.yaml").is_file()
            project = (parent / "pyproject.toml").is_file()
            if compose and project:
                return parent
    return _refuse("cannot find the repository")


def _refuse(reason: str) -> NoReturn:
    """Stop without writing a session.

    Args:
        reason: str - Why.

    Raises:
        SystemExit: Always. The message goes to stderr.

    """
    _ = sys.stderr.write(f"smr-review-session: {reason}\n")
    raise SystemExit(1)
