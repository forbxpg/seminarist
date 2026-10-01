"""Rows of sessions, attendance and board calls."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin
from smr.gradebook.infrastructure.models import EntryModel, ItemModel
from smr.roster.infrastructure.models import GroupModel, StudentModel

from ._base import SessionsBase
from ._tables import ATTENDANCE, BOARD_CALL, SCHEMA, SESSION


class SessionModel(UUIDPkMixin, TimestampMixin, SessionsBase):
    """A seminar session."""

    __tablename__: str = SESSION
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("char_length(topic) BETWEEN 1 AND 200", name="topic_length"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GroupModel.id, ondelete="CASCADE"),
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    topic: Mapped[str] = mapped_column(Text)
    attendance_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(ItemModel.id, ondelete="SET NULL"),
    )


class AttendanceModel(SessionsBase):
    """A student's status at a session."""

    __tablename__: str = ATTENDANCE
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            "status IN ('present', 'absent', 'excused')",
            name="status_known",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{SESSION}.id", ondelete="CASCADE"),
        primary_key=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text)


class BoardCallModel(UUIDPkMixin, SessionsBase):
    """A student called to the board."""

    __tablename__: str = BOARD_CALL
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("mode IN ('manual', 'random')", name="mode_known"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{SESSION}.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
        index=True,
    )
    mode: Mapped[str] = mapped_column(Text)
    task: Mapped[str | None] = mapped_column(Text)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(EntryModel.id, ondelete="SET NULL"),
    )
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
