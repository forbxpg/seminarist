"""The board: candidates with their chances, a draw, calls and their points."""

from __future__ import annotations

import dataclasses
import random
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from smr.core.audit import ActorKind, AuditEntry
from smr.gradebook.domain import WorkTypeKind
from smr.sessions.domain import (
    AttendanceStatus,
    BoardCall,
    BoardCallNotFoundError,
    BoardMode,
    NoCandidatesError,
    StudentNotInGroupError,
    draw,
)

from ._common import existing, open_group

if TYPE_CHECKING:
    from decimal import Decimal

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.gradebook.application.contracts import GradebookApi
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Student
    from smr.sessions.application.ports import (
        AttendanceRepository,
        BoardCallRepository,
        SessionRepository,
    )

_SYSTEM_RANDOM = random.SystemRandom()


@dataclass(frozen=True, slots=True)
class Candidate:
    """A student who may be called now.

    Attributes:
        student: Student - The student.
        probability: float - Their chance in a draw.
        calls: int - Their board calls this semester.

    """

    student: Student
    probability: float
    calls: int


@final
class BoardCandidates:
    """Who may be called now: present, not yet called in this session."""

    def __init__(
        self,
        sessions: SessionRepository,
        attendance: AttendanceRepository,
        calls: BoardCallRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._attendance: AttendanceRepository = attendance
        self._calls: BoardCallRepository = calls
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, session_id: uuid.UUID) -> list[Candidate]:
        """List them, the likeliest first.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.

        Returns:
            list[Candidate] - The candidates with their chances.

        """
        self._guard.require(actor)
        session = await existing(self._sessions, session_id)
        roster = await self._roster.students_of(session.group_id)
        marked = await self._attendance.of_session(session_id)
        called = {call.student_id for call in await self._calls.of_session(session_id)}
        eligible = {
            student.student_id: student
            for student in roster
            if student.student_id not in called
            and marked.get(student.student_id, AttendanceStatus.PRESENT)
            is AttendanceStatus.PRESENT
        }
        counts = await self._calls.counts_of_group(session.group_id)
        weights = await self._gradebook.priority_weights(
            session.group_id,
            counts,
            list(eligible),
        )
        candidates = [
            Candidate(student, weights[sid], counts.get(sid, 0))
            for sid, student in eligible.items()
        ]
        return sorted(candidates, key=lambda c: (-c.probability, c.student.full_name))


@final
class DrawToBoard:
    """Propose a student by weight; nothing is recorded until the teacher confirms."""

    def __init__(
        self,
        candidates: BoardCandidates,
        rng: random.Random = _SYSTEM_RANDOM,
    ) -> None:
        self._candidates: BoardCandidates = candidates
        self._rng: random.Random = rng

    async def __call__(self, actor: int, session_id: uuid.UUID) -> Candidate:
        """Draw one.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.

        Returns:
            Candidate - The proposed student.

        Raises:
            NoCandidatesError: If everyone present has already been called.

        """
        candidates = await self._candidates(actor, session_id)
        if not candidates:
            raise NoCandidatesError
        by_id = {c.student.student_id: c for c in candidates}
        drawn = draw({sid: c.probability for sid, c in by_id.items()}, self._rng)
        return by_id[drawn]


@final
class CallToBoard:
    """A student goes to the board: picked by hand, or a draw confirmed."""

    def __init__(
        self,
        sessions: SessionRepository,
        calls: BoardCallRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._calls: BoardCallRepository = calls
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(
        self,
        actor: int,
        session_id: uuid.UUID,
        student_id: uuid.UUID,
        mode: BoardMode,
        task: str | None,
    ) -> BoardCall:
        """Record the call.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.
            student_id: uuid.UUID - The student.
            mode: BoardMode - Picked by hand or drawn.
            task: str | None - What they solve.

        Returns:
            BoardCall - The call.

        Raises:
            StudentNotInGroupError: If the student is not on the group's roster.

        """
        self._guard.require(actor)
        async with self._uow:
            session = await existing(self._sessions, session_id)
            _ = await open_group(self._roster, session.group_id)
            student = await self._roster.student(student_id)
            if student is None or student.group_id != session.group_id:
                raise StudentNotInGroupError
            call = BoardCall(
                call_id=uuid.uuid4(),
                session_id=session_id,
                student_id=student_id,
                mode=mode,
                task=None if task is None else (" ".join(task.split()) or None),
                entry_id=None,
                called_at=self._clock.now(),
            )
            await self._calls.add(call)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "board.called",
                    "board_call",
                    str(call.call_id),
                    after={"student_id": str(student_id), "mode": mode.value},
                ),
            )
            await self._uow.commit()
        return call


@final
class GradeBoardCall:
    """Points for an answer at the board, in the group's board work type."""

    def __init__(
        self,
        sessions: SessionRepository,
        calls: BoardCallRepository,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._calls: BoardCallRepository = calls
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        call_id: uuid.UUID,
        points: Decimal,
        comment: str | None,
    ) -> BoardCall:
        """Grade it; a graded call gets its points changed.

        Args:
            actor: int - Teacher's Telegram id.
            call_id: uuid.UUID - The call.
            points: Decimal - Points for the answer.
            comment: str | None - A note for the student.

        Returns:
            BoardCall - The graded call.

        Raises:
            BoardCallNotFoundError: If there is no such call.
            ValueError: If the group has no board work type.

        """
        self._guard.require(actor)
        async with self._uow:
            call = await self._calls.get(call_id)
            if call is None:
                raise BoardCallNotFoundError
            if call.entry_id is not None:
                _ = await self._gradebook.edit_entry(
                    call.entry_id,
                    points,
                    comment=comment,
                    graded_by=actor,
                )
                await self._uow.commit()
                return call
            session = await existing(self._sessions, call.session_id)
            board = await self._gradebook.work_type_of_kind(
                session.group_id,
                WorkTypeKind.BOARD,
            )
            if board is None:
                msg = "the group has no board work type"
                raise ValueError(msg)
            entry = await self._gradebook.add_entry(
                call.student_id,
                board.work_type_id,
                points,
                comment=comment,
                graded_by=actor,
            )
            await self._calls.set_entry(call_id, entry.entry_id)
            await self._uow.commit()
        return dataclasses.replace(call, entry_id=entry.entry_id)


@final
class DeleteBoardCall:
    """A call made by mistake is deleted with its points."""

    def __init__(
        self,
        calls: BoardCallRepository,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._calls: BoardCallRepository = calls
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, call_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            call_id: uuid.UUID - The call.

        Raises:
            BoardCallNotFoundError: If there is no such call.

        """
        self._guard.require(actor)
        async with self._uow:
            call = await self._calls.get(call_id)
            if call is None:
                raise BoardCallNotFoundError
            if call.entry_id is not None:
                await self._gradebook.delete_entry(call.entry_id, graded_by=actor)
            await self._calls.delete(call_id)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "board.deleted",
                    "board_call",
                    str(call_id),
                    before={"student_id": str(call.student_id)},
                ),
            )
            await self._uow.commit()


@final
class SessionCalls:
    """A session's board calls with their students, in order."""

    def __init__(
        self,
        calls: BoardCallRepository,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._calls: BoardCallRepository = calls
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        session_id: uuid.UUID,
    ) -> list[tuple[BoardCall, Student]]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.

        Returns:
            list[tuple[BoardCall, Student]] - Each call and its student.

        """
        self._guard.require(actor)
        result: list[tuple[BoardCall, Student]] = []
        for call in await self._calls.of_session(session_id):
            student = await self._roster.student(call.student_id)
            if student is not None:
                result.append((call, student))
        return result
