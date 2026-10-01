"""The teacher's scheme of a group: work types and their caps."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import final

from smr.core.access import AdminGuard
from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.database import UnitOfWork
from smr.gradebook.application.ports import WorkTypeRepository
from smr.gradebook.domain import (
    DEFAULT_SCHEME,
    ScoringMode,
    WorkType,
    WorkTypeInUseError,
    WorkTypeKind,
    WorkTypeKindTakenError,
    WorkTypeNotFoundError,
)
from smr.roster.application.contracts import RosterApi

from ._groups import open_group


def _fields(work_type: WorkType) -> dict[str, object]:
    return {
        "title": work_type.title,
        "kind": work_type.kind.value,
        "mode": work_type.mode.value,
        "cap": str(work_type.cap),
        "in_priority": work_type.in_priority,
    }


def _audit(
    actor: int,
    action: str,
    before: WorkType | None,
    after: WorkType | None,
) -> AuditEntry:
    subject = after or before
    if subject is None:
        msg = "a change has a subject"
        raise ValueError(msg)
    return AuditEntry(
        actor_kind=ActorKind.ADMIN,
        actor_id=str(actor),
        action=action,
        entity="work_type",
        entity_id=str(subject.work_type_id),
        before=None if before is None else _fields(before),
        after=None if after is None else _fields(after),
    )


def _check_cap(cap: Decimal) -> None:
    if cap <= 0:
        msg = "a cap is positive"
        raise ValueError(msg)


@final
class ListWorkTypes:
    """A group's work types and the sum of their caps."""

    def __init__(self, work_types: WorkTypeRepository, guard: AdminGuard) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> Sequence[WorkType]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[WorkType] - In report order.

        """
        self._guard.require(actor)
        return await self._work_types.of_group(group_id)


@final
class CreateWorkType:
    """A new work type for a group."""

    def __init__(
        self,
        work_types: WorkTypeRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        *,
        title: str,
        kind: WorkTypeKind,
        mode: ScoringMode,
        cap: Decimal,
        in_priority: bool,
    ) -> WorkType:
        """Create it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            title: str - Its title.
            kind: WorkTypeKind - What it is for.
            mode: ScoringMode - How it is scored.
            cap: Decimal - Its cap.
            in_priority: bool - Whether it counts in the board priority.

        Returns:
            WorkType - The work type.

        Raises:
            ValueError: If the title is empty.
            WorkTypeKindTakenError: If the group already has the only one of the kind.

        """
        self._guard.require(actor)
        _check_cap(cap)
        clean = " ".join(title.split())
        if not clean:
            msg = "a work type has a title"
            raise ValueError(msg)
        async with self._uow:
            _ = await open_group(self._roster, group_id)
            if kind.is_single and await self._work_types.of_kind(group_id, kind):
                raise WorkTypeKindTakenError
            existing = await self._work_types.of_group(group_id)
            work_type = WorkType(
                work_type_id=uuid.uuid4(),
                group_id=group_id,
                title=clean,
                kind=kind,
                mode=mode,
                cap=cap,
                in_priority=in_priority,
                position=max((t.position for t in existing), default=0) + 1,
            )
            await self._work_types.add(work_type)
            await self._audit.record(
                _audit(actor, "work_type.created", None, work_type),
            )
            await self._uow.commit()
        return work_type


@final
class UpdateWorkType:
    """A work type's title, cap or priority flag changes; everyone is re-scored."""

    def __init__(
        self,
        work_types: WorkTypeRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        work_type_id: uuid.UUID,
        *,
        title: str,
        cap: Decimal,
        in_priority: bool,
    ) -> WorkType:
        """Change it.

        Args:
            actor: int - Teacher's Telegram id.
            work_type_id: uuid.UUID - It.
            title: str - Its title.
            cap: Decimal - Its cap.
            in_priority: bool - Whether it counts in the board priority.

        Returns:
            WorkType - The changed work type.

        Raises:
            WorkTypeNotFoundError: If there is no such work type.

        """
        self._guard.require(actor)
        _check_cap(cap)
        async with self._uow:
            before = await self._work_types.get(work_type_id)
            if before is None:
                raise WorkTypeNotFoundError
            _ = await open_group(self._roster, before.group_id)
            after = dataclasses.replace(
                before,
                title=" ".join(title.split()) or before.title,
                cap=cap,
                in_priority=in_priority,
            )
            await self._work_types.update(after)
            await self._audit.record(_audit(actor, "work_type.changed", before, after))
            await self._uow.commit()
        return after


@final
class DeleteWorkType:
    """A work type nobody has points for is removed."""

    def __init__(
        self,
        work_types: WorkTypeRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, work_type_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            work_type_id: uuid.UUID - It.

        Raises:
            WorkTypeNotFoundError: If there is no such work type.
            WorkTypeInUseError: If someone has points for it.

        """
        self._guard.require(actor)
        async with self._uow:
            before = await self._work_types.get(work_type_id)
            if before is None:
                raise WorkTypeNotFoundError
            _ = await open_group(self._roster, before.group_id)
            if await self._work_types.has_entries(work_type_id):
                raise WorkTypeInUseError
            await self._work_types.delete(work_type_id)
            await self._audit.record(_audit(actor, "work_type.deleted", before, None))
            await self._uow.commit()


@final
class ApplyDefaultScheme:
    """A group with no work types starts from the default 50-point scheme."""

    def __init__(
        self,
        work_types: WorkTypeRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> Sequence[WorkType]:
        """Apply it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[WorkType] - The created work types.

        Raises:
            ValueError: If the group already has work types.

        """
        self._guard.require(actor)
        async with self._uow:
            _ = await open_group(self._roster, group_id)
            if await self._work_types.of_group(group_id):
                msg = "the group already has a scheme"
                raise ValueError(msg)
            created: list[WorkType] = []
            for position, line in enumerate(DEFAULT_SCHEME, start=1):
                work_type = WorkType(
                    work_type_id=uuid.uuid4(),
                    group_id=group_id,
                    title=line.title,
                    kind=line.kind,
                    mode=line.mode,
                    cap=line.cap,
                    in_priority=True,
                    position=position,
                )
                await self._work_types.add(work_type)
                await self._audit.record(
                    _audit(actor, "work_type.created", None, work_type),
                )
                created.append(work_type)
            await self._uow.commit()
        return created
