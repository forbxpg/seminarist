"""ORM models of the roster."""

from __future__ import annotations

from ._base import METADATA, RosterBase
from ._group import GroupModel
from ._student import StudentModel
from ._tables import (
    GROUP,
    GROUP_INVITE_UNIQUE,
    SCHEMA,
    STUDENT,
    STUDENT_ACCOUNT_UNIQUE,
    STUDENT_NAME_UNIQUE,
)

__all__ = (
    "GROUP",
    "GROUP_INVITE_UNIQUE",
    "METADATA",
    "SCHEMA",
    "STUDENT",
    "STUDENT_ACCOUNT_UNIQUE",
    "STUDENT_NAME_UNIQUE",
    "GroupModel",
    "RosterBase",
    "StudentModel",
)
