"""Where the entries of the ledger are kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.gradebook.domain import GradeEntry


class EntryRepository(Protocol):
    """Every entry."""

    async def add(self, entry: GradeEntry) -> None:
        """Add an entry.

        Args:
            entry: GradeEntry - It.

        """
        ...

    async def get(self, entry_id: uuid.UUID) -> GradeEntry | None:
        """Read an entry.

        Args:
            entry_id: uuid.UUID - It.

        Returns:
            GradeEntry | None - It, or None.

        """
        ...

    async def for_item(
        self,
        student_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> GradeEntry | None:
        """Find a student's entry for an item.

        Args:
            student_id: uuid.UUID - The student.
            item_id: uuid.UUID - The item.

        Returns:
            GradeEntry | None - It, or None.

        """
        ...

    async def of_item(self, item_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List an item's entries.

        Args:
            item_id: uuid.UUID - The item.

        Returns:
            Sequence[GradeEntry] - Its entries.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List every entry of a group's work types.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[GradeEntry] - The entries.

        """
        ...

    async def of_student(self, student_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List a student's entries, newest first.

        Args:
            student_id: uuid.UUID - The student.

        Returns:
            Sequence[GradeEntry] - The entries.

        """
        ...

    async def update(self, entry: GradeEntry) -> None:
        """Store a changed entry.

        Args:
            entry: GradeEntry - It, changed.

        """
        ...

    async def delete(self, entry_id: uuid.UUID) -> None:
        """Delete an entry.

        Args:
            entry_id: uuid.UUID - It.

        """
        ...
