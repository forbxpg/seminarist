"""What a student sees of their score, and the teacher's sheet of the group."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import final

from smr.core.access import AdminGuard
from smr.gradebook.application.services import Ledger
from smr.gradebook.scoring import (
    Bucket,
    StudentScore,
    distribution,
    rank,
)
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import Student, StudentNotFoundError


@dataclass(frozen=True, slots=True)
class StudentReportView:
    """A student's own score, place and the group's spread.

    Attributes:
        score: StudentScore - Breakdown and total.
        place: int | None - Place in the group; none when the teacher hides ranks.
        group_size: int - Students in the group.
        buckets: tuple[Bucket, ...] | None - The group's spread; none with ranks hidden.

    """

    score: StudentScore
    place: int | None
    group_size: int
    buckets: tuple[Bucket, ...] | None


@dataclass(frozen=True, slots=True)
class SheetRow:
    """A line of the teacher's sheet.

    Attributes:
        student: Student - The student.
        score: StudentScore - Breakdown and total.
        place: int - Place in the group.

    """

    student: Student
    score: StudentScore
    place: int


@final
class StudentReport:
    """A bound student reads their own score; nobody else's."""

    def __init__(self, ledger: Ledger, roster: RosterApi) -> None:
        self._ledger: Ledger = ledger
        self._roster: RosterApi = roster

    async def __call__(self, tg_user_id: int, group_id: uuid.UUID) -> StudentReportView:
        """Read it.

        Args:
            tg_user_id: int - The asking account.
            group_id: uuid.UUID - The group it asks about.

        Returns:
            StudentReportView - The report.

        Raises:
            StudentNotFoundError: If the account holds no approved row of the group.

        """
        student = await self._roster.bound_student(tg_user_id, group_id)
        group = await self._roster.group(group_id)
        if student is None or group is None:
            raise StudentNotFoundError
        scores = await self._ledger.scores(group_id)
        mine = scores[student.student_id]
        if not group.settings.show_rank:
            return StudentReportView(mine, None, len(scores), None)
        places = rank({sid: score.total for sid, score in scores.items()})
        buckets = distribution((s.total for s in scores.values()), mine.cap_total)
        return StudentReportView(mine, places[student.student_id], len(scores), buckets)


@final
class GroupSheet:
    """The teacher's sheet: every student's breakdown, total and place."""

    def __init__(self, ledger: Ledger, roster: RosterApi, guard: AdminGuard) -> None:
        self._ledger: Ledger = ledger
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> list[SheetRow]:
        """Build it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            list[SheetRow] - In roster order.

        """
        self._guard.require(actor)
        scores = await self._ledger.scores(group_id)
        places = rank({sid: score.total for sid, score in scores.items()})
        return [
            SheetRow(student, scores[student.student_id], places[student.student_id])
            for student in await self._roster.students_of(group_id)
        ]
