"""Work types, graded items and the entries of the ledger."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type

from ._enums import ScoringMode, WorkTypeKind  # ruff: ignore[typing-only-first-party-import] -- dataclass field type


@dataclass(frozen=True, slots=True)
class WorkType:
    """A kind of work a group is scored for, with its cap.

    Attributes:
        work_type_id: uuid.UUID - The work type.
        group_id: uuid.UUID - Its group.
        title: str - As students see it, e.g. "Контрольные".
        kind: WorkTypeKind - What it is for.
        mode: ScoringMode - How its points become its score.
        cap: Decimal - The most it adds to the total.
        in_priority: bool - Whether it counts in the board priority.
        position: int - Order in reports.

    """

    work_type_id: uuid.UUID
    group_id: uuid.UUID
    title: str
    kind: WorkTypeKind
    mode: ScoringMode
    cap: Decimal
    in_priority: bool
    position: int


@dataclass(frozen=True, slots=True)
class GradeItem:
    """Something issued to the whole group: a homework, a test, a session.

    Attributes:
        item_id: uuid.UUID - The item.
        work_type_id: uuid.UUID - Its work type.
        title: str - E.g. "Контрольная 1".
        max_points: Decimal - The most a student may get for it.
        counts_from: datetime - From when it counts against everyone, e.g. a deadline.

    """

    item_id: uuid.UUID
    work_type_id: uuid.UUID
    title: str
    max_points: Decimal
    counts_from: datetime


@dataclass(frozen=True, slots=True)
class GradeEntry:
    """Points a student got.

    Attributes:
        entry_id: uuid.UUID - The entry.
        student_id: uuid.UUID - Whose.
        work_type_id: uuid.UUID - For which work type.
        item_id: uuid.UUID | None - For which item; none for accumulating points.
        points: Decimal - How many.
        excused: bool - The item does not count for this student at all.
        comment: str | None - The teacher's note.
        graded_by: int | None - Teacher's Telegram id; none when the system wrote it.
        graded_at: datetime - When.

    """

    entry_id: uuid.UUID
    student_id: uuid.UUID
    work_type_id: uuid.UUID
    item_id: uuid.UUID | None
    points: Decimal
    excused: bool
    comment: str | None
    graded_by: int | None
    graded_at: datetime
