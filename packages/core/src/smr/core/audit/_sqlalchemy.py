"""`AuditLog` over the SQLAlchemy session."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import insert

from ._table import AUDIT_LOG_TABLE

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ._entry import AuditEntry


@final
class SqlAlchemyAuditLog:
    """Audit log written in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def record(self, entry: AuditEntry) -> None:
        """Record an entry in the current transaction.

        Args:
            entry: AuditEntry - The change.

        """
        _ = await self._session.execute(
            insert(AUDIT_LOG_TABLE).values(
                actor_kind=entry.actor_kind.value,
                actor_id=entry.actor_id,
                action=entry.action,
                entity=entry.entity,
                entity_id=entry.entity_id,
                before=None if entry.before is None else dict(entry.before),
                after=None if entry.after is None else dict(entry.after),
            ),
        )
