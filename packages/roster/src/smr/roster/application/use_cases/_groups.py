"""The teacher's groups: create, tune, re-invite, archive; the purge of old ones."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, final

from smr.roster.domain import (
    Group,
    GroupArchivedError,
    GroupNotFoundError,
    GroupSettings,
    GroupStatus,
    new_invite_code,
)

from ._audit import by_admin, by_system

if TYPE_CHECKING:
    from collections.abc import Sequence

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.roster.application.ports import GroupRepository


async def _active(groups: GroupRepository, group_id: uuid.UUID) -> Group:
    group = await groups.get(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group


@final
class CreateGroup:
    """A new group with default settings and a fresh invite link."""

    def __init__(
        self,
        groups: GroupRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._groups: GroupRepository = groups
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        *,
        title: str,
        subject: str,
        semester: str,
    ) -> Group:
        """Create it.

        Args:
            actor: int - Teacher's Telegram id.
            title: str - Study group.
            subject: str - Subject.
            semester: str - Semester.

        Returns:
            Group - The new group.

        Raises:
            ValueError: If a field is empty.

        """
        self._guard.require(actor)
        fields = [" ".join(part.split()) for part in (title, subject, semester)]
        if not all(fields):
            msg = "title, subject and semester are required"
            raise ValueError(msg)
        group = Group(
            group_id=uuid.uuid4(),
            title=fields[0],
            subject=fields[1],
            semester=fields[2],
            invite_code=new_invite_code(),
            status=GroupStatus.ACTIVE,
            archived_at=None,
            settings=GroupSettings(),
        )
        async with self._uow:
            await self._groups.add(group)
            await self._audit.record(
                by_admin(actor, "group.created", "study_group", group.group_id),
            )
            await self._uow.commit()
        return group


@final
class ListGroups:
    """The teacher's groups, newest first."""

    def __init__(self, groups: GroupRepository, guard: AdminGuard) -> None:
        self._groups: GroupRepository = groups
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, *, include_archived: bool) -> Sequence[Group]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            include_archived: bool - Also the archived ones.

        Returns:
            Sequence[Group] - The groups.

        """
        self._guard.require(actor)
        return await self._groups.list(include_archived=include_archived)


@final
class UpdateGroupSettings:
    """New settings for an active group."""

    def __init__(
        self,
        groups: GroupRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._groups: GroupRepository = groups
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        settings: GroupSettings,
    ) -> Group:
        """Store them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            settings: GroupSettings - Its new settings.

        Returns:
            Group - The group with them; a value out of range is a `ValueError`.

        """
        self._guard.require(actor)
        _check(settings)
        async with self._uow:
            group = await _active(self._groups, group_id)
            await self._groups.save_settings(group_id, settings)
            await self._audit.record(
                by_admin(
                    actor,
                    "group.settings_changed",
                    "study_group",
                    group_id,
                    before=dataclasses.asdict(group.settings),
                    after=dataclasses.asdict(settings),
                ),
            )
            await self._uow.commit()
        return dataclasses.replace(group, settings=settings)


_WEEK_HOURS = 24 * 7
_TEN_YEARS_DAYS = 3650


def _check(settings: GroupSettings) -> None:
    if not 1 <= settings.reminder_hours <= _WEEK_HOURS:
        msg = "the reminder is due between 1 hour and a week before the deadline"
        raise ValueError(msg)
    if settings.board_weight < 0 or settings.score_weight < 0:
        msg = "priority weights are not negative"
        raise ValueError(msg)
    if not 1 <= settings.retention_days <= _TEN_YEARS_DAYS:
        msg = "an archived group is kept between 1 day and 10 years"
        raise ValueError(msg)


@final
class RotateInvite:
    """A new invite link; the old one stops working."""

    def __init__(
        self,
        groups: GroupRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._groups: GroupRepository = groups
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> str:
        """Replace it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            str - The new invite code.

        """
        self._guard.require(actor)
        code = new_invite_code()
        async with self._uow:
            _ = await _active(self._groups, group_id)
            await self._groups.set_invite(group_id, code)
            await self._audit.record(
                by_admin(actor, "group.invite_rotated", "study_group", group_id),
            )
            await self._uow.commit()
        return code


@final
class ArchiveGroup:
    """The semester is over: the group becomes read-only."""

    def __init__(
        self,
        groups: GroupRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._groups: GroupRepository = groups
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(self, actor: int, group_id: uuid.UUID) -> None:
        """Archive it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        """
        self._guard.require(actor)
        async with self._uow:
            _ = await _active(self._groups, group_id)
            await self._groups.archive(group_id, self._clock.now())
            await self._audit.record(
                by_admin(actor, "group.archived", "study_group", group_id),
            )
            await self._uow.commit()


@final
class GroupsDueForPurge:
    """Archived groups whose retention period is over."""

    def __init__(self, groups: GroupRepository, clock: Clock) -> None:
        self._groups: GroupRepository = groups
        self._clock: Clock = clock

    async def __call__(self) -> Sequence[Group]:
        """Find them.

        Returns:
            Sequence[Group] - Groups to purge now.

        """
        now = self._clock.now()
        archived = await self._groups.archived_before(now)
        return [
            group
            for group in archived
            if group.archived_at is not None
            and group.archived_at + timedelta(days=group.settings.retention_days) <= now
        ]


@final
class PurgeGroup:
    """Delete an archived group with everything tied to its roster."""

    def __init__(
        self,
        groups: GroupRepository,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> None:
        self._groups: GroupRepository = groups
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(self, group_id: uuid.UUID) -> None:
        """Delete it; the other packages' rows go with it by cascade.

        Args:
            group_id: uuid.UUID - The group.

        Raises:
            GroupNotFoundError: If there is no such group.
            ValueError: If the group is not archived.

        """
        async with self._uow:
            group = await self._groups.get(group_id)
            if group is None:
                raise GroupNotFoundError
            if group.is_active:
                msg = "only an archived group is purged"
                raise ValueError(msg)
            await self._groups.delete(group_id)
            await self._audit.record(by_system("group.purged", "study_group", group_id))
            await self._uow.commit()
