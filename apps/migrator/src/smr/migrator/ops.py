"""Helpers for revision files."""

from __future__ import annotations

import re

from alembic import op

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def create_schema(schema: str) -> None:
    """Create a package's schema.

    Args:
        schema: str - Schema name, lower-case letters, digits and `_`.

    """
    op.execute(f"CREATE SCHEMA {_identifier(schema)}")


def drop_schema(schema: str) -> None:
    """Drop a package's schema once its tables are gone.

    Args:
        schema: str - Schema name.

    """
    op.execute(f"DROP SCHEMA {_identifier(schema)}")


def _identifier(name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        msg = f"{name!r} is not a plain lower-case identifier"
        raise ValueError(msg)
    return name
