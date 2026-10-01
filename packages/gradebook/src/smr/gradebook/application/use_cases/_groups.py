"""The group a ledger change belongs to must be open."""

from __future__ import annotations

import uuid

from smr.roster.application.contracts import RosterApi
from smr.roster.domain import Group, GroupArchivedError, GroupNotFoundError


async def open_group(roster: RosterApi, group_id: uuid.UUID) -> Group:
    """Read a group that still takes changes.

    Args:
        roster: RosterApi - The roster.
        group_id: uuid.UUID - The group.

    Returns:
        Group - The active group.

    Raises:
        GroupNotFoundError: If there is no such group.
        GroupArchivedError: If the group is archived.

    """
    group = await roster.group(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group
