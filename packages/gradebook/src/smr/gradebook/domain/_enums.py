"""What a work type is and how it is scored."""

from __future__ import annotations

from enum import StrEnum


class WorkTypeKind(StrEnum):
    """What a work type is for; features find their work type by it."""

    HOMEWORK = "homework"
    TEST = "test"
    ATTENDANCE = "attendance"
    BOARD = "board"
    TEACHER = "teacher"
    OTHER = "other"

    @property
    def is_single(self) -> bool:
        """Tell whether a group may have only one work type of this kind.

        Returns:
            bool - True for attendance and board: features write there by kind.

        """
        return self in {WorkTypeKind.ATTENDANCE, WorkTypeKind.BOARD}


class ScoringMode(StrEnum):
    """How the points of a work type turn into its score."""

    PROPORTIONAL = "proportional"
    """The cap times the share of what could be earned so far."""

    ACCUMULATING = "accumulating"
    """The sum of the points, up to the cap."""
