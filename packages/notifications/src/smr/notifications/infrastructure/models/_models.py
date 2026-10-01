"""Rows of the outbox and of the preferences."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from smr.core.database import BigIntPkMixin, make_metadata
from smr.roster.infrastructure.models import StudentModel

SCHEMA = "notifications"
OUTBOX_DEDUPE_UNIQUE = "uq_outbox_dedupe_key"

METADATA = make_metadata(SCHEMA)


class NotificationsBase(DeclarativeBase):
    """Base of notifications' ORM models."""

    metadata: ClassVar[MetaData] = METADATA


class OutboxModel(BigIntPkMixin, NotificationsBase):
    """A notice to send."""

    __tablename__: str = "outbox"
    __table_args__: tuple[CheckConstraint | UniqueConstraint | Index, ...] = (
        UniqueConstraint("dedupe_key", name=OUTBOX_DEDUPE_UNIQUE),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        Index(
            "ix_outbox_waiting",
            "id",
            postgresql_where=text("sent_at IS NULL AND NOT gave_up"),
        ),
    )

    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    gave_up: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class PreferenceModel(NotificationsBase):
    """A student's reminder preference."""

    __tablename__: str = "preference"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
        primary_key=True,
    )
    reminders: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
