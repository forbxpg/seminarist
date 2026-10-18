"""Declarative base of the review's models."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy.orm import DeclarativeBase

from smr.core.database import make_metadata

from ._tables import SCHEMA

if TYPE_CHECKING:
    from sqlalchemy import MetaData

METADATA = make_metadata(SCHEMA)


class ReviewBase(DeclarativeBase):
    """Base of the review's ORM models."""

    metadata: ClassVar[MetaData] = METADATA
