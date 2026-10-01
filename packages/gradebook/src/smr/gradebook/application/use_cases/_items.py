"""Items the teacher issues by hand, such as tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from smr.core.audit import ActorKind, AuditEntry
from smr.gradebook.domain import ItemNotFoundError, WorkTypeNotFoundError

from ._groups import open_group

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.gradebook.application.ports import ItemRepository, WorkTypeRepository
    from smr.gradebook.application.services import Ledger
    from smr.gradebook.domain import GradeItem
    from smr.roster.application.contracts import RosterApi


@final
class ListItems:
    """A work type's items, oldest first."""

    def __init__(self, items: ItemRepository, guard: AdminGuard) -> None:
        self._items: ItemRepository = items
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        work_type_id: uuid.UUID,
    ) -> Sequence[GradeItem]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            work_type_id: uuid.UUID - The work type.

        Returns:
            Sequence[GradeItem] - Its items.

        """
        self._guard.require(actor)
        return await self._items.of_work_type(work_type_id)


@final
class CreateItem:
    """A new item, counting from now, e.g. "Контрольная 1"."""

    def __init__(
        self,
        ledger: Ledger,
        work_types: WorkTypeRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._ledger: Ledger = ledger
        self._work_types: WorkTypeRepository = work_types
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(
        self,
        actor: int,
        work_type_id: uuid.UUID,
        *,
        title: str,
        max_points: Decimal,
    ) -> GradeItem:
        """Issue it.

        Args:
            actor: int - Teacher's Telegram id.
            work_type_id: uuid.UUID - Its work type.
            title: str - Its title.
            max_points: Decimal - The most a student may get.

        Returns:
            GradeItem - The item.

        Raises:
            WorkTypeNotFoundError: If there is no such work type.
            ValueError: If the title is empty.

        """
        self._guard.require(actor)
        clean = " ".join(title.split())
        if not clean:
            msg = "an item has a title"
            raise ValueError(msg)
        async with self._uow:
            work_type = await self._work_types.get(work_type_id)
            if work_type is None:
                raise WorkTypeNotFoundError
            _ = await open_group(self._roster, work_type.group_id)
            item = await self._ledger.create_item(
                work_type_id,
                clean,
                max_points,
                self._clock.now(),
            )
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "item.created",
                    "grade_item",
                    str(item.item_id),
                    after={"title": clean, "max_points": str(max_points)},
                ),
            )
            await self._uow.commit()
        return item


@final
class DeleteItem:
    """An item withdrawn with everyone's points for it."""

    def __init__(
        self,
        ledger: Ledger,
        items: ItemRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._ledger: Ledger = ledger
        self._items: ItemRepository = items
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, item_id: uuid.UUID) -> None:
        """Withdraw it.

        Args:
            actor: int - Teacher's Telegram id.
            item_id: uuid.UUID - The item.

        Raises:
            ItemNotFoundError: If there is no such item.

        """
        self._guard.require(actor)
        async with self._uow:
            item = await self._items.get(item_id)
            if item is None:
                raise ItemNotFoundError
            await self._ledger.delete_item(item_id)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "item.deleted",
                    "grade_item",
                    str(item_id),
                    before={"title": item.title, "max_points": str(item.max_points)},
                ),
            )
            await self._uow.commit()
