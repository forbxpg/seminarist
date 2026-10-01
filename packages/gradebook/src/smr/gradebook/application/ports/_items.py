"""Where the graded items are kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.gradebook.domain import GradeItem


class ItemRepository(Protocol):
    """Every issued item."""

    async def add(self, item: GradeItem) -> None:
        """Add an item.

        Args:
            item: GradeItem - It.

        """
        ...

    async def get(self, item_id: uuid.UUID) -> GradeItem | None:
        """Read an item.

        Args:
            item_id: uuid.UUID - It.

        Returns:
            GradeItem | None - It, or None.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[GradeItem]:
        """List a group's items, oldest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[GradeItem] - Its items.

        """
        ...

    async def of_work_type(self, work_type_id: uuid.UUID) -> Sequence[GradeItem]:
        """List a work type's items, oldest first.

        Args:
            work_type_id: uuid.UUID - The work type.

        Returns:
            Sequence[GradeItem] - Its items.

        """
        ...

    async def update(self, item: GradeItem) -> None:
        """Store a changed item.

        Args:
            item: GradeItem - It, changed.

        """
        ...

    async def delete(self, item_id: uuid.UUID) -> None:
        """Delete an item with its entries.

        Args:
            item_id: uuid.UUID - It.

        """
        ...
