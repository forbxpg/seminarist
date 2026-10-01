"""The teacher's cards: create, fill, publish with a notice, take down, delete."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from smr.core.audit import ActorKind, AuditEntry
from smr.core.files import FileKind
from smr.materials.domain import (
    EmptyMaterialError,
    Material,
    MaterialFile,
    MaterialNotFoundError,
    MaterialStatus,
)
from smr.notifications.domain import NotificationKind
from smr.roster.domain import GroupArchivedError, GroupNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.core.files import FileStore
    from smr.materials.application.ports import (
        MaterialFileRepository,
        MaterialRepository,
    )
    from smr.notifications.application.contracts import NotificationsApi
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Group

MATERIAL_KINDS: frozenset[FileKind] = frozenset(FileKind)


@dataclass(frozen=True, slots=True)
class MaterialUpload:
    """A file the teacher sent for a card.

    Attributes:
        data: bytes - Its content.
        tg_file_id: str - Telegram's id, to send it again.

    """

    data: bytes
    tg_file_id: str


async def _open_group(roster: RosterApi, group_id: uuid.UUID) -> Group:
    group = await roster.group(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group


async def _card(materials: MaterialRepository, material_id: uuid.UUID) -> Material:
    material = await materials.get(material_id)
    if material is None:
        raise MaterialNotFoundError
    return material


def _audit(actor: int, action: str, material_id: uuid.UUID) -> AuditEntry:
    return AuditEntry(ActorKind.ADMIN, str(actor), action, "material", str(material_id))


@final
class CreateMaterial:
    """A new draft card."""

    def __init__(
        self,
        materials: MaterialRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(self, actor: int, group_id: uuid.UUID, title: str) -> Material:
        """Create it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            title: str - Its title, e.g. "Семинар 4".

        Returns:
            Material - The draft card.

        Raises:
            ValueError: If the title is empty.

        """
        self._guard.require(actor)
        clean = " ".join(title.split())
        if not clean:
            msg = "a card has a title"
            raise ValueError(msg)
        material = Material(
            material_id=uuid.uuid4(),
            group_id=group_id,
            title=clean,
            status=MaterialStatus.DRAFT,
            published_at=None,
            created_at=self._clock.now(),
        )
        async with self._uow:
            _ = await _open_group(self._roster, group_id)
            await self._materials.add(material)
            await self._audit.record(
                _audit(actor, "material.created", material.material_id),
            )
            await self._uow.commit()
        return material


@final
class AddMaterialFile:
    """A file joins a card."""

    def __init__(
        self,
        materials: MaterialRepository,
        stored: MaterialFileRepository,
        files: FileStore,
        uow: UnitOfWork,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._stored: MaterialFileRepository = stored
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(
        self,
        actor: int,
        material_id: uuid.UUID,
        upload: MaterialUpload,
    ) -> MaterialFile:
        """Add it.

        Args:
            actor: int - Teacher's Telegram id.
            material_id: uuid.UUID - The card.
            upload: MaterialUpload - The file.

        Returns:
            MaterialFile - The stored file.

        """
        self._guard.require(actor)
        async with self._uow:
            _ = await _card(self._materials, material_id)
            present = await self._stored.of_material(material_id)
            saved = await self._files.save(
                upload.data,
                accepted=MATERIAL_KINDS,
                now=self._clock.now(),
            )
            file = MaterialFile(
                file_id=uuid.uuid4(),
                material_id=material_id,
                tg_file_id=upload.tg_file_id,
                path=saved.relative_path,
                kind=saved.kind,
                size=saved.size,
                position=max((f.position for f in present), default=0) + 1,
            )
            await self._stored.add(file)
            await self._uow.commit()
        return file


@final
class RemoveMaterialFile:
    """A file leaves a card and the disk."""

    def __init__(
        self,
        stored: MaterialFileRepository,
        files: FileStore,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._stored: MaterialFileRepository = stored
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, file_id: uuid.UUID) -> None:
        """Remove it.

        Args:
            actor: int - Teacher's Telegram id.
            file_id: uuid.UUID - The file.

        Raises:
            MaterialNotFoundError: If there is no such file.

        """
        self._guard.require(actor)
        async with self._uow:
            file = await self._stored.get(file_id)
            if file is None:
                raise MaterialNotFoundError
            await self._stored.delete(file_id)
            await self._uow.commit()
        await self._files.delete(file.path)


@final
class PublishMaterial:
    """Students see the card; the group is told once."""

    def __init__(
        self,
        materials: MaterialRepository,
        stored: MaterialFileRepository,
        roster: RosterApi,
        notifications: NotificationsApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._stored: MaterialFileRepository = stored
        self._roster: RosterApi = roster
        self._notifications: NotificationsApi = notifications
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(self, actor: int, material_id: uuid.UUID) -> int:
        """Publish it.

        Args:
            actor: int - Teacher's Telegram id.
            material_id: uuid.UUID - The card.

        Returns:
            int - How many students were told.

        Raises:
            EmptyMaterialError: If the card has no file.

        """
        self._guard.require(actor)
        async with self._uow:
            material = await _card(self._materials, material_id)
            group = await _open_group(self._roster, material.group_id)
            if not await self._stored.of_material(material_id):
                raise EmptyMaterialError
            await self._materials.set_status(
                material_id,
                MaterialStatus.PUBLISHED,
                self._clock.now(),
            )
            told = await self._notifications.notify_group(
                material.group_id,
                NotificationKind.MATERIAL_PUBLISHED,
                {"title": material.title, "group": group.title},
                dedupe_key=f"material:{material_id}",
            )
            await self._audit.record(_audit(actor, "material.published", material_id))
            await self._uow.commit()
        return told


@final
class UnpublishMaterial:
    """The card goes back to a draft."""

    def __init__(
        self,
        materials: MaterialRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, material_id: uuid.UUID) -> None:
        """Take it down.

        Args:
            actor: int - Teacher's Telegram id.
            material_id: uuid.UUID - The card.

        """
        self._guard.require(actor)
        async with self._uow:
            _ = await _card(self._materials, material_id)
            await self._materials.set_status(material_id, MaterialStatus.DRAFT, None)
            await self._audit.record(_audit(actor, "material.unpublished", material_id))
            await self._uow.commit()


@final
class DeleteMaterial:
    """A card deleted with its files."""

    def __init__(
        self,
        materials: MaterialRepository,
        stored: MaterialFileRepository,
        files: FileStore,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._stored: MaterialFileRepository = stored
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, material_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            material_id: uuid.UUID - The card.

        """
        self._guard.require(actor)
        async with self._uow:
            _ = await _card(self._materials, material_id)
            paths = [f.path for f in await self._stored.of_material(material_id)]
            await self._materials.delete(material_id)
            await self._audit.record(_audit(actor, "material.deleted", material_id))
            await self._uow.commit()
        for path in paths:
            await self._files.delete(path)


@final
class ListMaterials:
    """Every card of a group, drafts included, for the teacher."""

    def __init__(
        self,
        materials: MaterialRepository,
        stored: MaterialFileRepository,
        guard: AdminGuard,
    ) -> None:
        self._materials: MaterialRepository = materials
        self._stored: MaterialFileRepository = stored
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
    ) -> list[tuple[Material, Sequence[MaterialFile]]]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            list[tuple[Material, Sequence[MaterialFile]]] - Each card with its files.

        """
        self._guard.require(actor)
        return [
            (material, await self._stored.of_material(material.material_id))
            for material in await self._materials.of_group(
                group_id,
                published_only=False,
            )
        ]


@final
class DeleteGroupMaterialFiles:
    """Before a group is purged, its materials leave the disk."""

    def __init__(self, stored: MaterialFileRepository, files: FileStore) -> None:
        self._stored: MaterialFileRepository = stored
        self._files: FileStore = files

    async def __call__(self, group_id: uuid.UUID) -> int:
        """Delete them; the rows go with the group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            int - How many files were deleted.

        """
        paths = await self._stored.paths_of_group(group_id)
        for path in paths:
            await self._files.delete(path)
        return len(paths)
