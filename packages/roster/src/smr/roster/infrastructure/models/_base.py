"""Declarative base of the roster's models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy.orm import DeclarativeBase

from smr.core.database import make_metadata

from ._tables import SCHEMA

if TYPE_CHECKING:
    from sqlalchemy import MetaData

METADATA = make_metadata(SCHEMA)


class RosterBase(DeclarativeBase):
    """Base of the roster's ORM models."""

    metadata: ClassVar[MetaData] = METADATA
