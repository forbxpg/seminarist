"""A session, attendance statuses and board calls."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from enum import StrEnum


class AttendanceStatus(StrEnum):
    """Whether a student was at a session."""

    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"


class BoardMode(StrEnum):
    """How a student came to the board."""

    MANUAL = "manual"
    RANDOM = "random"


@dataclass(frozen=True, slots=True)
class Session:
    """A seminar session.

    Attributes:
        session_id: uuid.UUID - The session.
        group_id: uuid.UUID - Its group.
        starts_at: datetime - When it starts.
        topic: str - What it is about.
        attendance_item_id: uuid.UUID | None - Its attendance item in the ledger.

    """

    session_id: uuid.UUID
    group_id: uuid.UUID
    starts_at: datetime
    topic: str
    attendance_item_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class BoardCall:
    """A student called to the board.

    Attributes:
        call_id: uuid.UUID - The call.
        session_id: uuid.UUID - At which session.
        student_id: uuid.UUID - Who.
        mode: BoardMode - Picked by hand or drawn.
        task: str | None - What they solved.
        entry_id: uuid.UUID | None - Their points in the ledger, once graded.
        called_at: datetime - When.

    """

    call_id: uuid.UUID
    session_id: uuid.UUID
    student_id: uuid.UUID
    mode: BoardMode
    task: str | None
    entry_id: uuid.UUID | None
    called_at: datetime
