"""The groups over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import final

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smr.roster.domain import Group, GroupSettings, GroupStatus
from smr.roster.infrastructure.models import GroupModel


@final
class SqlAlchemyGroups:
    """`GroupRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, group: Group) -> None:
        """Add a new group.

        Args:
            group: Group - The group.

        """
        self._session.add(
            GroupModel(
                id=group.group_id,
                title=group.title,
                subject=group.subject,
                semester=group.semester,
                invite_code=group.invite_code,
                status=group.status.value,
                archived_at=group.archived_at,
                **_settings_columns(group.settings),
            ),
        )
        await self._session.flush()

    async def get(self, group_id: uuid.UUID) -> Group | None:
        """Read a group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Group | None - It, or None when unknown.

        """
        row = await self._session.get(GroupModel, group_id, populate_existing=True)
        return None if row is None else to_group(row)

    async def by_invite(self, invite_code: str) -> Group | None:
        """Find a group by its invite code.

        Args:
            invite_code: str - Payload of the join link.

        Returns:
            Group | None - It, or None.

        """
        row = await self._session.scalar(
            select(GroupModel).where(GroupModel.invite_code == invite_code),
        )
        return None if row is None else to_group(row)

    async def list(self, *, include_archived: bool) -> Sequence[Group]:
        """List the groups, newest first.

        Args:
            include_archived: bool - Also the archived ones.

        Returns:
            Sequence[Group] - The groups.

        """
        query = select(GroupModel).order_by(GroupModel.created_at.desc())
        if not include_archived:
            query = query.where(GroupModel.status == GroupStatus.ACTIVE.value)
        return [to_group(row) for row in await self._session.scalars(query)]

    async def save_settings(self, group_id: uuid.UUID, settings: GroupSettings) -> None:
        """Store a group's settings.

        Args:
            group_id: uuid.UUID - The group.
            settings: GroupSettings - Its new settings.

        """
        _ = await self._session.execute(
            update(GroupModel)
            .where(GroupModel.id == group_id)
            .values(**_settings_columns(settings)),
        )

    async def set_invite(self, group_id: uuid.UUID, invite_code: str) -> None:
        """Replace a group's invite code.

        Args:
            group_id: uuid.UUID - The group.
            invite_code: str - The new code.

        """
        _ = await self._session.execute(
            update(GroupModel)
            .where(GroupModel.id == group_id)
            .values(invite_code=invite_code),
        )

    async def archive(self, group_id: uuid.UUID, now: datetime) -> None:
        """Archive a group.

        Args:
            group_id: uuid.UUID - The group.
            now: datetime - When.

        """
        _ = await self._session.execute(
            update(GroupModel)
            .where(GroupModel.id == group_id)
            .values(status=GroupStatus.ARCHIVED.value, archived_at=now),
        )

    async def archived_before(self, moment: datetime) -> Sequence[Group]:
        """List the groups archived before a moment.

        Args:
            moment: datetime - The moment.

        Returns:
            Sequence[Group] - Those groups.

        """
        rows = await self._session.scalars(
            select(GroupModel).where(
                GroupModel.status == GroupStatus.ARCHIVED.value,
                GroupModel.archived_at < moment,
            ),
        )
        return [to_group(row) for row in rows]

    async def delete(self, group_id: uuid.UUID) -> None:
        """Delete a group and its roster.

        Args:
            group_id: uuid.UUID - The group.

        """
        _ = await self._session.execute(
            delete(GroupModel).where(GroupModel.id == group_id),
        )


def _settings_columns(settings: GroupSettings) -> dict[str, object]:
    return {
        "reminder_hours": settings.reminder_hours,
        "board_weight": settings.board_weight,
        "score_weight": settings.score_weight,
        "retention_days": settings.retention_days,
        "show_rank": settings.show_rank,
    }


def to_group(row: GroupModel) -> Group:
    """Map a row to the domain group.

    Args:
        row: GroupModel - The row.

    Returns:
        Group - The group.

    """
    return Group(
        group_id=row.id,
        title=row.title,
        subject=row.subject,
        semester=row.semester,
        invite_code=row.invite_code,
        status=GroupStatus(row.status),
        archived_at=row.archived_at,
        settings=GroupSettings(
            reminder_hours=row.reminder_hours,
            board_weight=row.board_weight,
            score_weight=row.score_weight,
            retention_days=row.retention_days,
            show_rank=row.show_rank,
        ),
    )
