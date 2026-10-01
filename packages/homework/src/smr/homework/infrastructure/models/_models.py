"""Rows of assignments, submissions and their files."""

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
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from smr.core.database import TimestampMixin, UUIDPkMixin
from smr.gradebook.infrastructure.models import EntryModel, ItemModel, WorkTypeModel
from smr.roster.infrastructure.models import GroupModel, StudentModel

from ._base import HomeworkBase
from ._tables import (
    ASSIGNMENT,
    FILE,
    SCHEMA,
    SUBMISSION,
    SUBMISSION_ONE_DRAFT,
    SUBMISSION_ONE_LIVE,
)

_KINDS = "('jpg', 'png', 'webp', 'heic', 'pdf', 'docx')"


class AssignmentModel(UUIDPkMixin, TimestampMixin, HomeworkBase):
    """A homework set for a group."""

    __tablename__: str = ASSIGNMENT
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("max_points > 0", name="max_points_positive"),
        # A statement file is all three of its columns or none of them.
        CheckConstraint(
            "(statement_file_id IS NULL) = (statement_path IS NULL)",
            name="statement_path_with_id",
        ),
        CheckConstraint(
            "(statement_path IS NULL) = (statement_kind IS NULL)",
            name="statement_kind_with_path",
        ),
        CheckConstraint(
            f"statement_kind IS NULL OR statement_kind IN {_KINDS}",
            name="statement_kind_known",
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GroupModel.id, ondelete="CASCADE"),
        index=True,
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
    body: Mapped[str] = mapped_column(Text, server_default=text("''"))
    statement_file_id: Mapped[str | None] = mapped_column(Text)
    statement_path: Mapped[str | None] = mapped_column(Text)
    statement_kind: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    max_points: Mapped[Decimal] = mapped_column(Numeric(6, 2))


class SubmissionModel(UUIDPkMixin, TimestampMixin, HomeworkBase):
    """A version of a student's work."""

    __tablename__: str = SUBMISSION
    __table_args__: tuple[CheckConstraint | UniqueConstraint | Index, ...] = (
        UniqueConstraint("assignment_id", "student_id", "version", name="version_once"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'superseded', 'graded')",
            name="status_known",
        ),
        CheckConstraint(
            "(status = 'draft') = (sent_at IS NULL)",
            name="sent_unless_draft",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index(
            SUBMISSION_ONE_DRAFT,
            "assignment_id",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
        Index(
            SUBMISSION_ONE_LIVE,
            "assignment_id",
            "student_id",
            unique=True,
            postgresql_where=text("status IN ('submitted', 'graded')"),
        ),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{ASSIGNMENT}.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(StudentModel.id, ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_late: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(EntryModel.id, ondelete="SET NULL"),
    )


class FileModel(UUIDPkMixin, HomeworkBase):
    """A file of a submission."""

    __tablename__: str = FILE
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(f"kind IN {_KINDS}", name="kind_known"),
        CheckConstraint("size > 0", name="size_positive"),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.{SUBMISSION}.id", ondelete="CASCADE"),
        index=True,
    )
    tg_file_id: Mapped[str] = mapped_column(Text)
    tg_file_unique_id: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
