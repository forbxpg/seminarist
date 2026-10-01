"""What the session use cases share: the session and its open group."""

from __future__ import annotations

from typing import TYPE_CHECKING

from smr.roster.domain import GroupArchivedError, GroupNotFoundError
from smr.sessions.domain import SessionNotFoundError

if TYPE_CHECKING:
    import uuid

    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Group
    from smr.sessions.application.ports import SessionRepository
    from smr.sessions.domain import Session


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


async def existing(sessions: SessionRepository, session_id: uuid.UUID) -> Session:
    """Read a session that exists.

    Args:
        sessions: SessionRepository - The sessions.
        session_id: uuid.UUID - It.

    Returns:
        Session - It.

    Raises:
        SessionNotFoundError: If there is no such session.

    """
    session = await sessions.get(session_id)
    if session is None:
        raise SessionNotFoundError
    return session
