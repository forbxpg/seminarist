"""A student's score, work type by work type."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from smr.gradebook.domain import ScoringMode

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable
    from datetime import datetime

    from smr.gradebook.domain import GradeEntry, GradeItem, WorkType

_CENT = Decimal("0.01")
_ZERO = Decimal(0)


def _round(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class WorkTypeScore:
    """What a student has for one work type.

    Attributes:
        work_type: WorkType - The work type.
        score: Decimal - Its contribution to the total, to the cent.
        earned: Decimal - Points got.
        possible: Decimal - Points that could have been got so far; the cap for an
            accumulating work type.
        counted: bool - Whether anything counts yet.

    """

    work_type: WorkType
    score: Decimal
    earned: Decimal
    possible: Decimal
    counted: bool


@dataclass(frozen=True, slots=True)
class StudentScore:
    """A student's whole score.

    Attributes:
        student_id: uuid.UUID - The student.
        parts: tuple[WorkTypeScore, ...] - One per work type, in the work types' order.

    """

    student_id: uuid.UUID
    parts: tuple[WorkTypeScore, ...]

    @property
    def total(self) -> Decimal:
        """Sum the parts.

        Returns:
            Decimal - The total, to the cent.

        """
        return _round(sum((part.score for part in self.parts), _ZERO))

    @property
    def cap_total(self) -> Decimal:
        """Sum the caps.

        Returns:
            Decimal - The most the total can be.

        """
        return sum((part.work_type.cap for part in self.parts), _ZERO)

    @property
    def priority_share(self) -> float:
        """Tell the share of the in-priority caps the student has earned.

        Returns:
            float - From 0 to 1; 0 when no work type counts in the priority.

        """
        chosen = [part for part in self.parts if part.work_type.in_priority]
        caps = sum((part.work_type.cap for part in chosen), _ZERO)
        if caps == _ZERO:
            return 0.0
        return float(sum((part.score for part in chosen), _ZERO) / caps)


def score_student(
    student_id: uuid.UUID,
    work_types: Iterable[WorkType],
    items: Iterable[GradeItem],
    entries: Iterable[GradeEntry],
    now: datetime,
) -> StudentScore:
    """Score one student.

    Args:
        student_id: uuid.UUID - The student.
        work_types: Iterable[WorkType] - The group's work types, in report order.
        items: Iterable[GradeItem] - The group's issued items.
        entries: Iterable[GradeEntry] - The student's entries.
        now: datetime - The moment items start counting against.

    Returns:
        StudentScore - The score.

    """
    mine = [entry for entry in entries if entry.student_id == student_id]
    item_list = list(items)
    parts = tuple(
        _score_proportional(work_type, item_list, mine, now)
        if work_type.mode is ScoringMode.PROPORTIONAL
        else _score_accumulating(work_type, mine)
        for work_type in work_types
    )
    return StudentScore(student_id=student_id, parts=parts)


def _score_proportional(
    work_type: WorkType,
    items: list[GradeItem],
    entries: list[GradeEntry],
    now: datetime,
) -> WorkTypeScore:
    by_item = {entry.item_id: entry for entry in entries if entry.item_id is not None}
    earned = possible = _ZERO
    for item in items:
        if item.work_type_id != work_type.work_type_id:
            continue
        entry = by_item.get(item.item_id)
        if entry is not None and entry.excused:
            continue
        if entry is None and item.counts_from > now:
            continue
        possible += item.max_points
        earned += entry.points if entry is not None else _ZERO
    if possible == _ZERO:
        return WorkTypeScore(work_type, _ZERO, _ZERO, _ZERO, counted=False)
    score = _round(work_type.cap * earned / possible)
    return WorkTypeScore(work_type, score, earned, possible, counted=True)


def _score_accumulating(
    work_type: WorkType,
    entries: list[GradeEntry],
) -> WorkTypeScore:
    earned = sum(
        (
            entry.points
            for entry in entries
            if entry.work_type_id == work_type.work_type_id and entry.item_id is None
        ),
        _ZERO,
    )
    score = _round(min(work_type.cap, earned))
    return WorkTypeScore(
        work_type,
        score,
        earned,
        work_type.cap,
        counted=earned > _ZERO,
    )
