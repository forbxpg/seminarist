"""A student's side: published cards of their group and their files."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from smr.materials.application.ports import (
    MaterialFileRepository,
    MaterialRepository,
)
from smr.materials.domain import (
    Material,
    MaterialFile,
    MaterialNotFoundError,
    MaterialStatus,
)
from smr.roster.application.contracts import RosterApi


@final
class PublishedMaterials:
    """The cards a bound student sees, the newest first."""

    def __init__(self, materials: MaterialRepository, roster: RosterApi) -> None:
        self._materials: MaterialRepository = materials
        self._roster: RosterApi = roster

    async def __call__(
        self,
        tg_user_id: int,
        group_id: uuid.UUID,
    ) -> Sequence[Material]:
        """List them.

        Args:
            tg_user_id: int - The asking account.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Material] - Published cards; none for an account not bound here.

        """
        if await self._roster.bound_student(tg_user_id, group_id) is None:
            return []
        return await self._materials.of_group(group_id, published_only=True)


@final
class MaterialFiles:
    """A published card's files for a student of its group."""

    def __init__(
        self,
        materials: MaterialRepository,
        stored: MaterialFileRepository,
        roster: RosterApi,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._stored: MaterialFileRepository = stored
        self._roster: RosterApi = roster

    async def __call__(
        self,
        tg_user_id: int,
        material_id: uuid.UUID,
    ) -> tuple[Material, Sequence[MaterialFile]]:
        """Give them.

        Args:
            tg_user_id: int - The asking account.
            material_id: uuid.UUID - The card.

        Returns:
            tuple[Material, Sequence[MaterialFile]] - The card and its files.

        Raises:
            MaterialNotFoundError: If there is no such published card for this account.

        """
        material = await self._materials.get(material_id)
        if material is None or material.status is not MaterialStatus.PUBLISHED:
            raise MaterialNotFoundError
        if await self._roster.bound_student(tg_user_id, material.group_id) is None:
            raise MaterialNotFoundError
        return material, await self._stored.of_material(material_id)
