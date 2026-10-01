"""Assignments, submissions and their files."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from enum import StrEnum

from smr.core.files import FileKind  # ruff: ignore[typing-only-first-party-import] -- dataclass field type


class SubmissionStatus(StrEnum):
    """Where a version of a student's work stands."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    SUPERSEDED = "superseded"
    GRADED = "graded"


@dataclass(frozen=True, slots=True)
class StatementFile:
    """The file of an assignment's statement.

    Attributes:
        tg_file_id: str - Telegram's id, to send it again.
        path: str - Where it is on disk.
        kind: FileKind - What it is.

    """

    tg_file_id: str
    path: str
    kind: FileKind


@dataclass(frozen=True, slots=True)
class Assignment:
    """A homework set for a group.

    Attributes:
        assignment_id: uuid.UUID - The assignment.
        group_id: uuid.UUID - Its group.
        work_type_id: uuid.UUID - The work type it is scored in.
        item_id: uuid.UUID | None - Its item in the ledger.
        title: str - E.g. "ДЗ к семинару 3".
        body: str - The statement as text.
        statement: StatementFile | None - The statement as a file.
        deadline: datetime - When it is due.
        max_points: Decimal - The most a student may get.

    """

    assignment_id: uuid.UUID
    group_id: uuid.UUID
    work_type_id: uuid.UUID
    item_id: uuid.UUID | None
    title: str
    body: str
    statement: StatementFile | None
    deadline: datetime
    max_points: Decimal


@dataclass(frozen=True, slots=True)
class SubmissionFile:
    """A file of a submission.

    Attributes:
        file_id: uuid.UUID - The file.
        submission_id: uuid.UUID - Its submission.
        tg_file_id: str - Telegram's id, to send it again.
        tg_file_unique_id: str - Telegram's stable id, to spot the same file twice.
        path: str - Where it is on disk.
        kind: FileKind - What it is.
        size: int - Bytes.
        sha256: str - Hex digest.
        position: int - Order in the submission.
        sent_at: datetime - When the student sent it, by Telegram's clock.

    """

    file_id: uuid.UUID
    submission_id: uuid.UUID
    tg_file_id: str
    tg_file_unique_id: str
    path: str
    kind: FileKind
    size: int
    sha256: str
    position: int
    sent_at: datetime


@dataclass(frozen=True, slots=True)
class Submission:
    """A version of a student's work.

    Attributes:
        submission_id: uuid.UUID - The version.
        assignment_id: uuid.UUID - Its assignment.
        student_id: uuid.UUID - Whose.
        version: int - 1, 2, …
        status: SubmissionStatus - Draft, submitted, superseded or graded.
        sent_at: datetime | None - When it was sent; none for a draft.
        is_late: bool - Sent after the deadline.
        entry_id: uuid.UUID | None - Its grade in the ledger.

    """

    submission_id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    status: SubmissionStatus
    sent_at: datetime | None
    is_late: bool
    entry_id: uuid.UUID | None
