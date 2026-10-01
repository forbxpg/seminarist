"""A group: a study group taking one subject in one semester."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from enum import StrEnum


class GroupStatus(StrEnum):
    """Whether the group is in progress."""

    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class GroupSettings:
    """What the teacher tunes for a group.

    Attributes:
        reminder_hours: int - Hours before a deadline the reminder goes out.
        board_weight: float - How much past board calls lower a student's priority.
        score_weight: float - How much a high score lowers a student's priority.
        retention_days: int - Days the data of an archived group is kept.
        show_rank: bool - Whether students see their place in the group.

    """

    reminder_hours: int = 24
    board_weight: float = 1.0
    score_weight: float = 1.0
    retention_days: int = 180
    show_rank: bool = True


@dataclass(frozen=True, slots=True)
class Group:
    """A group.

    Attributes:
        group_id: uuid.UUID - The group.
        title: str - Study group, e.g. "К01-261".
        subject: str - Subject, e.g. "Дискретная математика".
        semester: str - Semester, e.g. "осень 2026".
        invite_code: str - Payload of the join link.
        status: GroupStatus - Active or archived.
        archived_at: datetime | None - When it was archived.
        settings: GroupSettings - What the teacher tuned.

    """

    group_id: uuid.UUID
    title: str
    subject: str
    semester: str
    invite_code: str
    status: GroupStatus
    archived_at: datetime | None
    settings: GroupSettings

    @property
    def name(self) -> str:
        """Tell the group as people say it.

        Returns:
            str - "К01-261 · Дискретная математика · осень 2026".

        """
        return f"{self.title} · {self.subject} · {self.semester}"

    @property
    def is_active(self) -> bool:
        """Tell whether the group is in progress.

        Returns:
            bool - True unless archived.

        """
        return self.status is GroupStatus.ACTIVE
