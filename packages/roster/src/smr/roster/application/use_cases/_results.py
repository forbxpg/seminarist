"""What the roster's use cases return beyond its entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smr.roster.domain import Group, Student


@dataclass(frozen=True, slots=True)
class ImportResult:
    """How a pasted roster went in.

    Attributes:
        added: int - New names.
        skipped: int - Names the group already had.

    """

    added: int
    skipped: int


@dataclass(frozen=True, slots=True)
class Membership:
    """A roster row of an account, with its group.

    Attributes:
        group: Group - The group.
        student: Student - The row.

    """

    group: Group
    student: Student
