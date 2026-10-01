"""Errors of sessions."""

from __future__ import annotations


class SessionsError(Exception):
    """Base of the sessions' errors."""


class SessionNotFoundError(SessionsError):
    """No such session."""


class BoardCallNotFoundError(SessionsError):
    """No such board call."""


class StudentNotInGroupError(SessionsError):
    """The student is not on this group's roster."""


class NoCandidatesError(SessionsError):
    """Nobody left to call to the board in this session."""
