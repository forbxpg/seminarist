"""The migrator's command line: upgrade to the newest revision, or downgrade one."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

_CONFIG_ENV = "MIGRATOR_ALEMBIC_INI"


def alembic_config() -> Config:
    """Locate `alembic.ini`: `MIGRATOR_ALEMBIC_INI`, else the working directory.

    Returns:
        Config - Alembic configuration.

    """
    return Config(os.environ.get(_CONFIG_ENV, str(Path.cwd() / "alembic.ini")))


def main(argv: list[str] | None = None) -> None:
    """Run a migrator command.

    Args:
        argv: list[str] | None - Arguments; the process's when none.

    """
    parser = argparse.ArgumentParser(prog="smr-migrator")
    commands = parser.add_subparsers(dest="command", required=True)
    _ = commands.add_parser("upgrade", help="apply every revision up to the newest")
    down = commands.add_parser("downgrade", help="undo revisions down to a target")
    _ = down.add_argument("target", help="revision id, or -1 for the last one")
    arguments = parser.parse_args(argv)
    chosen: str = arguments.command  # pyright: ignore[reportAny] -- argparse
    config = alembic_config()
    if chosen == "upgrade":
        command.upgrade(config, "heads")
    else:
        target: str = arguments.target  # pyright: ignore[reportAny] -- argparse
        command.downgrade(config, target)
