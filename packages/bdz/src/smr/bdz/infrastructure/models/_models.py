"""Rows of a БДЗ, its point scheme and students' versions."""

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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.gradebook.infrastructure.models import ItemModel, WorkTypeModel
from smr.roster.infrastructure.models import GroupModel, StudentModel

from ._base import BdzBase
from ._tables import ASSIGNMENT, SUBMISSION, SUBMISSION_ONE_LIVE, TASK

_POINTS = Numeric(6, 2)


class AssignmentModel(BdzBase):
    """One published БДЗ."""

    __tablename__: str = ASSIGNMENT
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint("max_points > 0", name="max_points_positive"),
        CheckConstraint("statement_pages >= 1", name="statement_pages_positive"),
        CheckConstraint("solutions_pages >= 1", name="solutions_pages_positive"),
    )

    bdz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GroupModel.id, ondelete="CASCADE"),
    )
    work_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(WorkTypeModel.id, ondelete="RESTRICT"),
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(ItemModel.id, ondelete="SET NULL"),
    )
    title: Mapped[str] = mapped_column(Text)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_points: Mapped[Decimal] = mapped_column(_POINTS)
    statement_path: Mapped[str] = mapped_column(Text)
    statement_tg_file_id: Mapped[str] = mapped_column(Text)
    statement_pages: Mapped[int] = mapped_column(Integer)
    solutions_path: Mapped[str] = mapped_column(Text)
    solutions_tg_file_id: Mapped[str] = mapped_column(Text)
    solutions_pages: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskModel(BdzBase):
    """One task of a point scheme."""

    __tablename__: str = TASK
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("number BETWEEN 1 AND 50", name="number_in_range"),
        CheckConstraint("max_points > 0", name="max_points_positive"),
    )

    bdz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(AssignmentModel.bdz_id, ondelete="CASCADE"),
        primary_key=True,
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_points: Mapped[Decimal] = mapped_column(_POINTS)


class SubmissionModel(BdzBase):
    """One version of a student's PDF."""

    __tablename__: str = SUBMISSION
    __table_args__: tuple[CheckConstraint | UniqueConstraint | Index, ...] = (
        CheckConstraint("status IN ('live', 'superseded')", name="status_known"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("pages >= 1", name="pages_positive"),
        UniqueConstraint(
            "bdz_id",
            "student_id",
            "version",
            name="uq_submission_version",
        ),
        Index(
            SUBMISSION_ONE_LIVE,
            "bdz_id",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'live'"),
        ),
        Index("ix_submission_bdz_status", "bdz_id", "status"),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    bdz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(AssignmentModel.bdz_id, ondelete="CASCADE"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    tg_file_id: Mapped[str] = mapped_column(Text)
    tg_file_unique_id: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(Text)
    pages: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_late: Mapped[bool] = mapped_column(Boolean)
