"""A roster row."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin

from ._base import RosterBase
from ._tables import (
    GROUP,
    SCHEMA,
    STUDENT,
    STUDENT_ACCOUNT_UNIQUE,
    STUDENT_JOURNAL_UNIQUE,
    STUDENT_NAME_UNIQUE,
)


class StudentModel(UUIDPkMixin, TimestampMixin, RosterBase):
    """A student of a roster and the Telegram account tied to it."""

    __tablename__: str = STUDENT
    __table_args__: tuple[CheckConstraint | UniqueConstraint, ...] = (
        UniqueConstraint("group_id", "full_name", name=STUDENT_NAME_UNIQUE),
        UniqueConstraint("group_id", "tg_user_id", name=STUDENT_ACCOUNT_UNIQUE),
        UniqueConstraint("group_id", "journal_no", name=STUDENT_JOURNAL_UNIQUE),
        CheckConstraint("journal_no BETWEEN 1 AND 999", name="journal_no_range"),
        CheckConstraint("char_length(full_name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint(
            "binding IN ('unbound', 'pending', 'bound')",
            name="binding_known",
        ),
        CheckConstraint(
            "(binding = 'unbound') = (tg_user_id IS NULL)",
            name="account_iff_claimed",
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{GROUP}.id", ondelete="CASCADE"),
        index=True,
    )
    full_name: Mapped[str] = mapped_column(Text, comment="As the teacher typed it")
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    binding: Mapped[str] = mapped_column(Text, server_default=text("'unbound'"))
    binding_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    consent_version: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_no: Mapped[int | None] = mapped_column(
        Integer,
        comment="Number in the group's journal; personal variants follow it",
    )
