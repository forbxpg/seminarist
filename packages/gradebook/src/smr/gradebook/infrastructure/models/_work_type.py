"""A work type row."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin
from smr.roster.infrastructure.models import GroupModel

from ._base import GradebookBase
from ._tables import WORK_TYPE, WORK_TYPE_SINGLE_KIND


class WorkTypeModel(UUIDPkMixin, TimestampMixin, GradebookBase):
    """A kind of work a group is scored for."""

    __tablename__: str = WORK_TYPE
    __table_args__: tuple[CheckConstraint | Index, ...] = (
        CheckConstraint(
            "kind IN ('homework', 'test', 'attendance', 'board', 'teacher', 'other')",
            name="kind_known",
        ),
        CheckConstraint(
            "mode IN ('proportional', 'accumulating')",
            name="mode_known",
        ),
        CheckConstraint("cap > 0", name="cap_positive"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 100", name="title_length"),
        Index(
            WORK_TYPE_SINGLE_KIND,
            "group_id",
            "kind",
            unique=True,
            postgresql_where=text("kind IN ('attendance', 'board')"),
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GroupModel.id, ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    cap: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    in_priority: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"))
