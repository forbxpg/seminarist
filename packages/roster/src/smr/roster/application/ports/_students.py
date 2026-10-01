"""Where the roster rows are kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from smr.roster.domain import BindingStatus, Student


class StudentRepository(Protocol):
    """Every roster row."""

    async def add_many(self, group_id: uuid.UUID, names: Sequence[str]) -> int:
        """Add names to a group's roster; names it already has are skipped.

        Args:
            group_id: uuid.UUID - The group.
            names: Sequence[str] - Tidy distinct names.

        Returns:
            int - How many were added.

        """
        ...

    async def get(self, student_id: uuid.UUID) -> Student | None:
        """Read a roster row.

        Args:
            student_id: uuid.UUID - The row.

        Returns:
            Student | None - It, or None when unknown.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Student]:
        """List a group's roster by name.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Student] - The roster.

        """
        ...

    async def of_account(self, tg_user_id: int) -> Sequence[Student]:
        """List every row a Telegram account claims or holds.

        Args:
            tg_user_id: int - Telegram user id.

        Returns:
            Sequence[Student] - The rows.

        """
        ...

    async def pending(self) -> Sequence[Student]:
        """List the rows waiting for the teacher, oldest claim first.

        Returns:
            Sequence[Student] - The rows.

        """
        ...

    async def claim(
        self,
        student_id: uuid.UUID,
        tg_user_id: int,
        consent_version: str,
        now: datetime,
    ) -> bool:
        """Claim a row for an account, only if nobody holds it.

        Args:
            student_id: uuid.UUID - The row.
            tg_user_id: int - The claiming account.
            consent_version: str - The privacy notice it accepted.
            now: datetime - When.

        Returns:
            bool - False when someone already claims or holds the row.

        """
        ...

    async def set_binding(self, student_id: uuid.UUID, binding: BindingStatus) -> None:
        """Move a claimed row to another binding state, keeping its account.

        Args:
            student_id: uuid.UUID - The row.
            binding: BindingStatus - Pending or bound.

        """
        ...

    async def release(self, student_id: uuid.UUID) -> None:
        """Unbind a row: forget its account and consent.

        Args:
            student_id: uuid.UUID - The row.

        """
        ...

    async def rename(self, student_id: uuid.UUID, full_name: str) -> None:
        """Rename a row.

        Args:
            student_id: uuid.UUID - The row.
            full_name: str - Its new tidy name.

        """
        ...

    async def delete(self, student_id: uuid.UUID) -> None:
        """Delete a row.

        Args:
            student_id: uuid.UUID - The row.

        """
        ...
