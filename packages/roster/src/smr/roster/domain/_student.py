"""A roster row and its Telegram binding."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from enum import StrEnum


class BindingStatus(StrEnum):
    """How far a roster row is tied to a Telegram account."""

    UNBOUND = "unbound"
    PENDING = "pending"
    BOUND = "bound"


@dataclass(frozen=True, slots=True)
class Student:
    """A student of a group's roster.

    Attributes:
        student_id: uuid.UUID - The roster row.
        group_id: uuid.UUID - Its group.
        full_name: str - As the teacher typed it.
        tg_user_id: int | None - The Telegram account claiming or holding it.
        binding: BindingStatus - Unbound, waiting for the teacher, or bound.
        binding_requested_at: datetime | None - When it was claimed.
        consent_version: str | None - The privacy notice the student accepted.
        consent_at: datetime | None - When.
        journal_no: int | None - The number in the group's journal; variants of
            personal tasks are computed from it.

    """

    student_id: uuid.UUID
    group_id: uuid.UUID
    full_name: str
    tg_user_id: int | None
    binding: BindingStatus
    binding_requested_at: datetime | None
    consent_version: str | None
    consent_at: datetime | None
    journal_no: int | None = None
