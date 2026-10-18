"""The rules of groups and rosters."""

from __future__ import annotations

from ._consent import CONSENT_VERSION
from ._errors import (
    AlreadyBoundError,
    DuplicateNameError,
    GroupArchivedError,
    GroupNotFoundError,
    InviteNotFoundError,
    NameTakenError,
    NotPendingError,
    RosterError,
    StudentNotFoundError,
)
from ._group import Group, GroupSettings, GroupStatus
from ._invite import new_invite_code
from ._names import MAX_NAME_LENGTH, normalize_name, parse_roster
from ._student import BindingStatus, Student

__all__ = (
    "CONSENT_VERSION",
    "MAX_NAME_LENGTH",
    "AlreadyBoundError",
    "BindingStatus",
    "DuplicateNameError",
    "Group",
    "GroupArchivedError",
    "GroupNotFoundError",
    "GroupSettings",
    "GroupStatus",
    "InviteNotFoundError",
    "NameTakenError",
    "NotPendingError",
    "RosterError",
    "Student",
    "StudentNotFoundError",
    "new_invite_code",
    "normalize_name",
    "parse_roster",
)
