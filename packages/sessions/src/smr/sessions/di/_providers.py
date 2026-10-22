"""Sessions' repositories and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.sessions.application.ports import (
    AttendanceRepository,
    BoardCallRepository,
    SessionRepository,
)
from smr.sessions.application.use_cases import (
    AttendanceSheet,
    BoardCandidates,
    CallToBoard,
    CreateSession,
    DeleteBoardCall,
    DeleteSession,
    DrawToBoard,
    GradeBoardCall,
    ListSessions,
    MarkAttendance,
    SessionCalls,
    UpdateSession,
)
from smr.sessions.infrastructure.repositories import (
    SqlAlchemyAttendance,
    SqlAlchemyBoardCalls,
    SqlAlchemySessions,
)


@final
class SessionsProvider(Provider):
    """Everything of sessions, built per update or task."""

    scope = Scope.REQUEST

    sessions = provide(SqlAlchemySessions, provides=SessionRepository)
    attendance = provide(SqlAlchemyAttendance, provides=AttendanceRepository)
    calls = provide(SqlAlchemyBoardCalls, provides=BoardCallRepository)

    @provide
    def draw(self, candidates: BoardCandidates) -> DrawToBoard:
        """Draw with the operating system's randomness.

        Args:
            candidates: BoardCandidates - Who may be called.

        Returns:
            DrawToBoard - The use case.

        """
        return DrawToBoard(candidates)

    use_cases = provide_all(
        AttendanceSheet,
        BoardCandidates,
        CallToBoard,
        CreateSession,
        DeleteBoardCall,
        DeleteSession,
        GradeBoardCall,
        ListSessions,
        MarkAttendance,
        SessionCalls,
        UpdateSession,
    )
