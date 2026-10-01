"""A graded item row."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin

from ._base import GradebookBase
from ._tables import ITEM, SCHEMA, WORK_TYPE


class ItemModel(UUIDPkMixin, TimestampMixin, GradebookBase):
    """Something issued to a whole group."""

    __tablename__: str = ITEM
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("max_points > 0", name="max_points_positive"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
    )

    work_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{WORK_TYPE}.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(Text)
    max_points: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    counts_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
