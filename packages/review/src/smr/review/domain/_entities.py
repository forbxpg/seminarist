"""A verdict, its tasks and an appeal."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type

from ._enums import (  # ruff: ignore[typing-only-first-party-import] -- dataclass field type
    AppealStatus,
    GraderKind,
    VerdictStatus,
)


@dataclass(frozen=True, slots=True)
class SchemeTask:
    """One task of a point scheme.

    Attributes:
        number: int - Its number, from 1.
        max_points: Decimal - The most it is worth.

    """

    number: int
    max_points: Decimal


@dataclass(frozen=True, slots=True)
class TaskVerdict:
    """Points and an explanation for one task.

    Attributes:
        number: int - The task.
        points: Decimal - What it scored.
        max_points: Decimal - What it is worth.
        explanation: str - Written to the student.
        unreadable: bool - A page of it could not be read.
        unsure: bool - The grader is not confident.
        manipulation: bool - The work addresses the grader.
        pages: tuple[int, ...] - Pages the task was found on.

    """

    number: int
    points: Decimal
    max_points: Decimal
    explanation: str
    unreadable: bool
    unsure: bool
    manipulation: bool
    pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Verdict:
    """One grading of one version of a work.

    Attributes:
        verdict_id: uuid.UUID - It.
        source: str - Which kind of work, `bdz` for now.
        work_id: uuid.UUID - The version.
        work_sha256: str - The file the verdict is about.
        task_ref: uuid.UUID - The assignment.
        student_ref: uuid.UUID - The roster row, never a name.
        grader_kind: GraderKind - Agent or teacher.
        grader: str - Model name, or the teacher's Telegram id.
        status: VerdictStatus - Where it is.
        total: Decimal - The sum of the tasks.
        max_points: Decimal - The scheme's sum.
        summary: str - A short overview; may be empty for a teacher.
        pages_seen: int - How many pages the work has.
        created_at: datetime - When it was recorded.
        published_at: datetime | None - When the student was told.
        tasks: tuple[TaskVerdict, ...] - One row per task.

    """

    verdict_id: uuid.UUID
    source: str
    work_id: uuid.UUID
    work_sha256: str
    task_ref: uuid.UUID
    student_ref: uuid.UUID
    grader_kind: GraderKind
    grader: str
    status: VerdictStatus
    total: Decimal
    max_points: Decimal
    summary: str
    pages_seen: int
    created_at: datetime
    published_at: datetime | None
    tasks: tuple[TaskVerdict, ...]


@dataclass(frozen=True, slots=True)
class Appeal:
    """A student's disagreement with an agent's verdict.

    Attributes:
        appeal_id: uuid.UUID - It.
        verdict_id: uuid.UUID - The verdict it disputes.
        text: str - What the student disagrees with.
        status: AppealStatus - Open or resolved.
        filed_at: datetime - When.
        resolved_at: datetime | None - When the teacher decided.
        resolution_verdict_id: uuid.UUID | None - The teacher's verdict.

    """

    appeal_id: uuid.UUID
    verdict_id: uuid.UUID
    text: str
    status: AppealStatus
    filed_at: datetime
    resolved_at: datetime | None
    resolution_verdict_id: uuid.UUID | None
