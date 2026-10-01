"""A group row."""

from __future__ import annotations

from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin

from ._base import RosterBase
from ._tables import GROUP, GROUP_INVITE_UNIQUE


class GroupModel(UUIDPkMixin, TimestampMixin, RosterBase):
    """A study group taking one subject in one semester, and its settings."""

    __tablename__: str = GROUP
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        UniqueConstraint("invite_code", name=GROUP_INVITE_UNIQUE),
        CheckConstraint("status IN ('active', 'archived')", name="status_known"),
        CheckConstraint(
            "(status = 'archived') = (archived_at IS NOT NULL)",
            name="archived_at_iff_archived",
        ),
        CheckConstraint(
            "reminder_hours BETWEEN 1 AND 168",
            name="reminder_hours_range",
        ),
        CheckConstraint(
            "board_weight >= 0 AND score_weight >= 0",
            name="weights_positive",
        ),
        CheckConstraint("retention_days BETWEEN 1 AND 3650", name="retention_range"),
    )

    title: Mapped[str] = mapped_column(Text, comment="Study group")
    subject: Mapped[str] = mapped_column(Text, comment="Subject")
    semester: Mapped[str] = mapped_column(Text, comment="Semester")
    invite_code: Mapped[str] = mapped_column(Text, comment="Payload of the join link")
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_hours: Mapped[int] = mapped_column(Integer, server_default=text("24"))
    board_weight: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    score_weight: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    retention_days: Mapped[int] = mapped_column(Integer, server_default=text("180"))
    show_rank: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
