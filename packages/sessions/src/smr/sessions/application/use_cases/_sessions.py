"""The teacher's sessions: create, list, delete."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import final

from smr.core.access import AdminGuard
from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.database import UnitOfWork
from smr.gradebook.application.contracts import GradebookApi
from smr.roster.application.contracts import RosterApi
from smr.sessions.application.ports import BoardCallRepository, SessionRepository
from smr.sessions.domain import Session

from ._common import existing, open_group


@final
class CreateSession:
    """A new session of a group."""

    def __init__(
        self,
        sessions: SessionRepository,
        roster: RosterApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._roster: RosterApi = roster
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        *,
        starts_at: datetime,
        topic: str,
    ) -> Session:
        """Create it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            starts_at: datetime - When it starts.
            topic: str - What it is about.

        Returns:
            Session - The session.

        """
        self._guard.require(actor)
        session = Session(
            session_id=uuid.uuid4(),
            group_id=group_id,
            starts_at=starts_at,
            topic=" ".join(topic.split()) or "Семинар",
            attendance_item_id=None,
        )
        async with self._uow:
            _ = await open_group(self._roster, group_id)
            await self._sessions.add(session)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "session.created",
                    "seminar_session",
                    str(session.session_id),
                ),
            )
            await self._uow.commit()
        return session


@final
class ListSessions:
    """A group's sessions, the latest first."""

    def __init__(self, sessions: SessionRepository, guard: AdminGuard) -> None:
        self._sessions: SessionRepository = sessions
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> Sequence[Session]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Session] - The sessions.

        """
        self._guard.require(actor)
        return await self._sessions.of_group(group_id)


@final
class DeleteSession:
    """A session deleted with its attendance, calls and their points."""

    def __init__(
        self,
        sessions: SessionRepository,
        calls: BoardCallRepository,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._sessions: SessionRepository = sessions
        self._calls: BoardCallRepository = calls
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, session_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            session_id: uuid.UUID - The session.

        """
        self._guard.require(actor)
        async with self._uow:
            session = await existing(self._sessions, session_id)
            if session.attendance_item_id is not None:
                await self._gradebook.delete_item(session.attendance_item_id)
            for call in await self._calls.of_session(session_id):
                if call.entry_id is not None:
                    await self._gradebook.delete_entry(call.entry_id, graded_by=actor)
            await self._sessions.delete(session_id)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "session.deleted",
                    "seminar_session",
                    str(session_id),
                ),
            )
            await self._uow.commit()
