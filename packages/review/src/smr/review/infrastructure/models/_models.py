"""Rows of verdicts, their tasks and appeals."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ._base import ReviewBase
from ._tables import APPEAL, VERDICT, VERDICT_ONE_CURRENT, VERDICT_TASK

_POINTS = Numeric(6, 2)
_STATUSES = "('published', 'manual', 'appealed', 'superseded', 'final', 'voided')"
_CURRENT = "('published', 'manual', 'appealed', 'final')"


class VerdictModel(ReviewBase):
    """One grading of one version of a work."""

    __tablename__: str = VERDICT
    __table_args__: tuple[CheckConstraint | Index, ...] = (
        CheckConstraint("source IN ('bdz')", name="source_known"),
        CheckConstraint(f"status IN {_STATUSES}", name="status_known"),
        CheckConstraint(
            "grader_kind IN ('agent', 'teacher')",
            name="grader_kind_known",
        ),
        CheckConstraint("char_length(summary) <= 1000", name="summary_length"),
        CheckConstraint("char_length(grader) BETWEEN 1 AND 64", name="grader_length"),
        CheckConstraint("total >= 0 AND max_points > 0", name="points_sane"),
        CheckConstraint("pages_seen >= 1", name="pages_seen_positive"),
        Index(
            VERDICT_ONE_CURRENT,
            "source",
            "work_id",
            unique=True,
            postgresql_where=text(f"status IN {_CURRENT}"),
        ),
        Index("ix_verdict_source_status", "source", "status"),
    )

    verdict_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    work_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    work_sha256: Mapped[str] = mapped_column(Text)
    task_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    student_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    grader_kind: Mapped[str] = mapped_column(Text)
    grader: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(_POINTS)
    max_points: Mapped[Decimal] = mapped_column(_POINTS)
    summary: Mapped[str] = mapped_column(Text)
    pages_seen: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VerdictTaskModel(ReviewBase):
    """One task of a verdict."""

    __tablename__: str = VERDICT_TASK
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("points >= 0 AND max_points > 0", name="points_sane"),
        CheckConstraint("NOT manipulation OR points = 0", name="manipulation_is_zero"),
        CheckConstraint("char_length(explanation) <= 1500", name="explanation_length"),
    )

    verdict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(VerdictModel.verdict_id, ondelete="CASCADE"),
        primary_key=True,
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    points: Mapped[Decimal] = mapped_column(_POINTS)
    max_points: Mapped[Decimal] = mapped_column(_POINTS)
    explanation: Mapped[str] = mapped_column(Text)
    unreadable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    unsure: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    manipulation: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    pages: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        server_default=text("'{}'::integer[]"),
    )


class AppealModel(ReviewBase):
    """A student's appeal of one verdict."""

    __tablename__: str = APPEAL
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("status IN ('open', 'resolved')", name="status_known"),
        CheckConstraint('char_length("text") BETWEEN 10 AND 2000', name="text_length"),
    )

    appeal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    verdict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(VerdictModel.verdict_id, ondelete="CASCADE"),
        unique=True,
    )
    body: Mapped[str] = mapped_column("text", Text)
    status: Mapped[str] = mapped_column(Text)
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_verdict_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(VerdictModel.verdict_id, ondelete="SET NULL"),
    )
