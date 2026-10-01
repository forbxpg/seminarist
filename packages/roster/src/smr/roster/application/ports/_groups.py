"""Where the groups are kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from smr.roster.domain import Group, GroupSettings


class GroupRepository(Protocol):
    """Every group."""

    async def add(self, group: Group) -> None:
        """Add a new group.

        Args:
            group: Group - The group.

        """
        ...

    async def get(self, group_id: uuid.UUID) -> Group | None:
        """Read a group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Group | None - It, or None when unknown.

        """
        ...

    async def by_invite(self, invite_code: str) -> Group | None:
        """Find a group by its invite code.

        Args:
            invite_code: str - Payload of the join link.

        Returns:
            Group | None - It, or None when no group has this code.

        """
        ...

    async def list(self, *, include_archived: bool) -> Sequence[Group]:
        """List the groups, newest first.

        Args:
            include_archived: bool - Also the archived ones.

        Returns:
            Sequence[Group] - The groups.

        """
        ...

    async def save_settings(self, group_id: uuid.UUID, settings: GroupSettings) -> None:
        """Store a group's settings.

        Args:
            group_id: uuid.UUID - The group.
            settings: GroupSettings - Its new settings.

        """
        ...

    async def set_invite(self, group_id: uuid.UUID, invite_code: str) -> None:
        """Replace a group's invite code.

        Args:
            group_id: uuid.UUID - The group.
            invite_code: str - The new code.

        """
        ...

    async def archive(self, group_id: uuid.UUID, now: datetime) -> None:
        """Archive a group.

        Args:
            group_id: uuid.UUID - The group.
            now: datetime - When.

        """
        ...

    async def archived_before(self, moment: datetime) -> Sequence[Group]:
        """List the groups archived before a moment.

        Args:
            moment: datetime - The moment.

        Returns:
            Sequence[Group] - Those groups.

        """
        ...

    async def delete(self, group_id: uuid.UUID) -> None:
        """Delete a group and its roster.

        Args:
            group_id: uuid.UUID - The group.

        """
        ...
