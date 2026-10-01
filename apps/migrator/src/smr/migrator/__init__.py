"""Migrator: one Alembic chain over every package's revisions."""

from __future__ import annotations

from ._cli import main
from ._metadata import all_metadata

__all__ = ("all_metadata", "main")
