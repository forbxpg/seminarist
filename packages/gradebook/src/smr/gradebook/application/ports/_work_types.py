"""Where the work types are kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.gradebook.domain import WorkType, WorkTypeKind


class WorkTypeRepository(Protocol):
    """Every group's work types."""

    async def add(self, work_type: WorkType) -> None:
        """Add a work type.

        Args:
            work_type: WorkType - It.

        """
        ...

    async def get(self, work_type_id: uuid.UUID) -> WorkType | None:
        """Read a work type.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            WorkType | None - It, or None.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[WorkType]:
        """List a group's work types in report order.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[WorkType] - Its work types.

        """
        ...

    async def of_kind(
        self,
        group_id: uuid.UUID,
        kind: WorkTypeKind,
    ) -> Sequence[WorkType]:
        """List a group's work types of a kind.

        Args:
            group_id: uuid.UUID - The group.
            kind: WorkTypeKind - The kind.

        Returns:
            Sequence[WorkType] - Those work types.

        """
        ...

    async def update(self, work_type: WorkType) -> None:
        """Store a changed work type.

        Args:
            work_type: WorkType - It, changed.

        """
        ...

    async def delete(self, work_type_id: uuid.UUID) -> None:
        """Delete a work type.

        Args:
            work_type_id: uuid.UUID - It.

        """
        ...

    async def has_entries(self, work_type_id: uuid.UUID) -> bool:
        """Tell whether a work type has any points.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            bool - True when an entry refers to it.

        """
        ...
