"""Ports of materials."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from smr.materials.domain import Material, MaterialFile, MaterialStatus


class MaterialRepository(Protocol):
    """Every card."""

    async def add(self, material: Material) -> None:
        """Add a card.

        Args:
            material: Material - It.

        """
        ...

    async def get(self, material_id: uuid.UUID) -> Material | None:
        """Read a card.

        Args:
            material_id: uuid.UUID - It.

        Returns:
            Material | None - It, or None.

        """
        ...

    async def of_group(
        self,
        group_id: uuid.UUID,
        *,
        published_only: bool,
    ) -> Sequence[Material]:
        """List a group's cards, the newest first.

        Args:
            group_id: uuid.UUID - The group.
            published_only: bool - Only those students see.

        Returns:
            Sequence[Material] - The cards.

        """
        ...

    async def set_status(
        self,
        material_id: uuid.UUID,
        status: MaterialStatus,
        published_at: datetime | None,
    ) -> None:
        """Publish or unpublish a card.

        Args:
            material_id: uuid.UUID - It.
            status: MaterialStatus - Its new status.
            published_at: datetime | None - When it was published; none for a draft.

        """
        ...

    async def delete(self, material_id: uuid.UUID) -> None:
        """Delete a card with its files' rows.

        Args:
            material_id: uuid.UUID - It.

        """
        ...


class MaterialFileRepository(Protocol):
    """Every file of every card."""

    async def add(self, file: MaterialFile) -> None:
        """Add a file.

        Args:
            file: MaterialFile - It.

        """
        ...

    async def get(self, file_id: uuid.UUID) -> MaterialFile | None:
        """Read a file.

        Args:
            file_id: uuid.UUID - It.

        Returns:
            MaterialFile | None - It, or None.

        """
        ...

    async def of_material(self, material_id: uuid.UUID) -> Sequence[MaterialFile]:
        """List a card's files in order.

        Args:
            material_id: uuid.UUID - The card.

        Returns:
            Sequence[MaterialFile] - Its files.

        """
        ...

    async def delete(self, file_id: uuid.UUID) -> None:
        """Delete a file's row.

        Args:
            file_id: uuid.UUID - It.

        """
        ...

    async def paths_of_group(self, group_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of a group's files.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[str] - The paths.

        """
        ...
