"""Attendance: the teacher marks who is here, and the ledger follows."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from decimal import Decimal
from typing import final

from smr.core.access import AdminGuard
from smr.core.database import UnitOfWork
from smr.gradebook.application.contracts import GradebookApi
from smr.gradebook.domain import WorkTypeKind
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import Student
from smr.sessions.application.ports import AttendanceRepository, SessionRepository
from smr.sessions.domain import AttendanceStatus, Session, StudentNotInGroupError

from ._common import existing, open_group
from ._labels import attendance_title, moscow_day, sync_attendance_titles

_ONE = Decimal(1)
_ZERO = Decimal(0)


@final
class AttendanceSheet:
    """The roster with each student's status; unmarked ones are proposed present."""

    def __init__(
        self,
        sessions: SessionRepository,
        attendance: AttendanceRepository,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._attendance: AttendanceRepository = attendance
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        session_id: uuid.UUID,
    ) -> list[tuple[Student, AttendanceStatus]]:
        """Read it.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.

        Returns:
            list[tuple[Student, AttendanceStatus]] - In roster order.

        """
        self._guard.require(actor)
        session = await existing(self._sessions, session_id)
        marked = await self._attendance.of_session(session_id)
        return [
            (student, marked.get(student.student_id, AttendanceStatus.PRESENT))
            for student in await self._roster.students_of(session.group_id)
        ]


@final
class MarkAttendance:
    """The teacher saves the session's attendance; points follow in the ledger."""

    def __init__(
        self,
        sessions: SessionRepository,
        attendance: AttendanceRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._attendance: AttendanceRepository = attendance
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        session_id: uuid.UUID,
        statuses: Mapping[uuid.UUID, AttendanceStatus],
    ) -> None:
        """Save it.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.
            statuses: Mapping[uuid.UUID, AttendanceStatus] - Each student's status.

        Raises:
            StudentNotInGroupError: If a student is not on the group's roster.

        """
        self._guard.require(actor)
        async with self._uow:
            session = await existing(self._sessions, session_id)
            _ = await open_group(self._roster, session.group_id)
            roster = {
                s.student_id for s in await self._roster.students_of(session.group_id)
            }
            if not set(statuses) <= roster:
                raise StudentNotInGroupError
            await self._attendance.save(session_id, statuses)
            item_id = await self._attendance_item(session)
            await sync_attendance_titles(
                self._sessions,
                self._gradebook,
                session.group_id,
                moscow_day(session.starts_at),
            )
            if item_id is not None:
                for student_id, status in statuses.items():
                    _ = await self._gradebook.set_entry(
                        student_id,
                        item_id,
                        _ONE if status is AttendanceStatus.PRESENT else _ZERO,
                        excused=status is AttendanceStatus.EXCUSED,
                        comment=None,
                        graded_by=actor,
                    )
            await self._uow.commit()

    async def _attendance_item(self, session: Session) -> uuid.UUID | None:
        """Find or issue the session's attendance item.

        Args:
            session: Session - The session.

        Returns:
            uuid.UUID | None - The item; none when the group has no attendance type.

        """
        if session.attendance_item_id is not None:
            return session.attendance_item_id
        work_type = await self._gradebook.work_type_of_kind(
            session.group_id,
            WorkTypeKind.ATTENDANCE,
        )
        if work_type is None:
            return None
        same_day = [
            other
            for other in await self._sessions.of_group(session.group_id)
            if moscow_day(other.starts_at) == moscow_day(session.starts_at)
        ]
        item = await self._gradebook.create_item(
            work_type.work_type_id,
            attendance_title(session.starts_at, with_time=len(same_day) > 1),
            _ONE,
            session.starts_at,
        )
        await self._sessions.set_attendance_item(session.session_id, item.item_id)
        return item.item_id
