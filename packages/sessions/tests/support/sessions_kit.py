"""Sessions' use cases over one session, for integration tests."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, final

import pytest

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.sessions.application.use_cases import (
    AttendanceSheet,
    BoardCandidates,
    CallToBoard,
    CreateSession,
    DeleteBoardCall,
    DeleteSession,
    DrawToBoard,
    GradeBoardCall,
    MarkAttendance,
    SessionCalls,
)
from smr.sessions.infrastructure.repositories import (
    SqlAlchemyAttendance,
    SqlAlchemyBoardCalls,
    SqlAlchemySessions,
)

if TYPE_CHECKING:
    from gradebook_kit import Gradebook
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("Sessions", "sessions")


@final
class Sessions:
    """Sessions' use cases bound to one session, next to the roster and the ledger."""

    def __init__(self, session: AsyncSession, gradebook: Gradebook) -> None:
        sessions = SqlAlchemySessions(session)
        attendance = SqlAlchemyAttendance(session)
        calls = SqlAlchemyBoardCalls(session)
        uow = SqlAlchemyUnitOfWork(session)
        audit = SqlAlchemyAuditLog(session)
        guard = AdminGuard({1})
        roster = gradebook.roster
        ledger = gradebook.ledger
        self.gradebook: Gradebook = gradebook
        self.create: CreateSession = CreateSession(
            sessions,
            roster.api,
            uow,
            audit,
            guard,
        )
        self.delete: DeleteSession = DeleteSession(
            sessions,
            calls,
            ledger,
            uow,
            audit,
            guard,
        )
        self.sheet: AttendanceSheet = AttendanceSheet(
            sessions,
            attendance,
            roster.api,
            guard,
        )
        self.mark: MarkAttendance = MarkAttendance(
            sessions,
            attendance,
            roster.api,
            ledger,
            uow,
            guard,
        )
        self.candidates: BoardCandidates = BoardCandidates(
            sessions,
            attendance,
            calls,
            roster.api,
            ledger,
            guard,
        )
        self.draw: DrawToBoard = DrawToBoard(self.candidates, random.Random(1))  # ruff: ignore[suspicious-non-cryptographic-random-usage] -- reproducible draws
        self.call: CallToBoard = CallToBoard(
            sessions,
            calls,
            roster.api,
            uow,
            audit,
            guard,
            roster.clock,
        )
        self.grade: GradeBoardCall = GradeBoardCall(sessions, calls, ledger, uow, guard)
        self.delete_call: DeleteBoardCall = DeleteBoardCall(
            calls,
            ledger,
            uow,
            audit,
            guard,
        )
        self.calls: SessionCalls = SessionCalls(calls, roster.api, guard)


@pytest.fixture
def sessions(session: AsyncSession, gradebook: Gradebook) -> Sessions:
    """Give sessions' use cases over the test's session."""
    return Sessions(session, gradebook)
