"""The rules of sessions, attendance and board calls."""

from __future__ import annotations

from ._draw import draw
from ._entities import AttendanceStatus, BoardCall, BoardMode, Session
from ._errors import (
    BoardCallNotFoundError,
    NoCandidatesError,
    SessionNotFoundError,
    SessionsError,
    StudentNotInGroupError,
)

__all__ = (
    "AttendanceStatus",
    "BoardCall",
    "BoardCallNotFoundError",
    "BoardMode",
    "NoCandidatesError",
    "Session",
    "SessionNotFoundError",
    "SessionsError",
    "StudentNotInGroupError",
    "draw",
)
