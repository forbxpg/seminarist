"""A БДЗ and a student's version of it."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type

from smr.review.domain import SchemeTask  # ruff: ignore[typing-only-first-party-import] -- dataclass field type

from ._enums import SubmissionStatus  # ruff: ignore[typing-only-first-party-import] -- dataclass field type


@dataclass(frozen=True, slots=True)
class BdzDraft:
    """What the teacher typed before the files are stored.

    Attributes:
        title: str - Its title.
        deadline: datetime - When it is due.
        work_type_id: uuid.UUID - The proportional work type.
        tasks: tuple[SchemeTask, ...] - The point scheme.

    """

    title: str
    deadline: datetime
    work_type_id: uuid.UUID
    tasks: tuple[SchemeTask, ...]


@dataclass(frozen=True, slots=True)
class Bdz:
    """One published БДЗ.

    Attributes:
        bdz_id: uuid.UUID - It.
        group_id: uuid.UUID - Its group.
        work_type_id: uuid.UUID - Its work type.
        item_id: uuid.UUID | None - The ledger item.
        title: str - Its title.
        deadline: datetime - When it is due.
        max_points: Decimal - The sum of the scheme.
        statement_path: str - The statement PDF.
        statement_tg_file_id: str - Telegram's id for the statement.
        statement_pages: int - How many pages it has.
        solutions_path: str | None - The solutions PDF; None when the agent solves
            the tasks itself.
        solutions_tg_file_id: str | None - Telegram's id for the solutions.
        solutions_pages: int | None - How many pages they have.
        created_at: datetime - When it was published.

    """

    bdz_id: uuid.UUID
    group_id: uuid.UUID
    work_type_id: uuid.UUID
    item_id: uuid.UUID | None
    title: str
    deadline: datetime
    max_points: Decimal
    statement_path: str
    statement_tg_file_id: str
    statement_pages: int
    solutions_path: str | None
    solutions_tg_file_id: str | None
    solutions_pages: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BdzSubmission:
    """One version of a student's PDF.

    Attributes:
        submission_id: uuid.UUID - It. This is the review's work id.
        bdz_id: uuid.UUID - The БДЗ.
        student_id: uuid.UUID - The roster row.
        version: int - 1, 2, …
        status: SubmissionStatus - Live or superseded.
        path: str - The FileStore path.
        tg_file_id: str - Telegram's id.
        tg_file_unique_id: str - Telegram's stable id.
        size: int - Bytes.
        sha256: str - The file.
        pages: int - How many pages.
        sent_at: datetime - Telegram's message date.
        is_late: bool - Sent after the deadline.

    """

    submission_id: uuid.UUID
    bdz_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    status: SubmissionStatus
    path: str
    tg_file_id: str
    tg_file_unique_id: str
    size: int
    sha256: str
    pages: int
    sent_at: datetime
    is_late: bool
