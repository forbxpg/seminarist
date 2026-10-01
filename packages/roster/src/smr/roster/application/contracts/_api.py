"""The roster as its neighbours see it: read-only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.roster.domain import Group, Student


class RosterApi(Protocol):
    """Read the roster from another package."""

    async def group(self, group_id: uuid.UUID) -> Group | None:
        """Read a group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Group | None - It, or None when unknown.

        """
        ...

    async def student(self, student_id: uuid.UUID) -> Student | None:
        """Read a roster row.

        Args:
            student_id: uuid.UUID - The row.

        Returns:
            Student | None - It, or None when unknown.

        """
        ...

    async def students_of(self, group_id: uuid.UUID) -> Sequence[Student]:
        """List a group's roster by name.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Student] - The roster.

        """
        ...

    async def bound_student(
        self,
        tg_user_id: int,
        group_id: uuid.UUID,
    ) -> Student | None:
        """Find the row an account holds, approved, in a group.

        Args:
            tg_user_id: int - Telegram user id.
            group_id: uuid.UUID - The group.

        Returns:
            Student | None - The bound row, or None.

        """
        ...
