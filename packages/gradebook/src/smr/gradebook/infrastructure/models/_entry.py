"""An entry row of the ledger."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import UUIDPkMixin
from smr.roster.infrastructure.models import StudentModel

from ._base import GradebookBase
from ._tables import ENTRY, ENTRY_ITEM_UNIQUE, ITEM, SCHEMA, WORK_TYPE


class EntryModel(UUIDPkMixin, GradebookBase):
    """Points a student got."""

    __tablename__: str = ENTRY
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        UniqueConstraint("student_id", "item_id", name=ENTRY_ITEM_UNIQUE),
        CheckConstraint("points >= 0", name="points_not_negative"),
        CheckConstraint(
            "NOT excused OR (points = 0 AND item_id IS NOT NULL)",
            name="excused_is_an_item_at_zero",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
        index=True,
    )
    work_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{WORK_TYPE}.id", ondelete="CASCADE"),
        index=True,
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{ITEM}.id", ondelete="CASCADE"),
        index=True,
    )
    points: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    excused: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    comment: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[int | None] = mapped_column(BigInteger)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
