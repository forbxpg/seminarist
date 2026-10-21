"""Errors of groups and rosters."""

from __future__ import annotations


class RosterError(Exception):
    """Base of the roster's errors."""


class GroupNotFoundError(RosterError):
    """No such group."""


class GroupArchivedError(RosterError):
    """The group is archived: it is read-only and takes no one new."""


class InviteNotFoundError(RosterError):
    """The invite link is unknown or was replaced."""


class StudentNotFoundError(RosterError):
    """No such roster row."""


class NameTakenError(RosterError):
    """Someone has already claimed this name."""


class AlreadyBoundError(RosterError):
    """This Telegram account already holds a row of the group."""


class DuplicateNameError(RosterError):
    """The group already has a student with this name."""


class JournalNumberTakenError(RosterError):
    """Another student of the group already has this journal number."""


class NotPendingError(RosterError):
    """The row is not waiting for the teacher's decision."""
