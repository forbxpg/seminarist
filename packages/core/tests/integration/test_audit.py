"""The audit log over a real database."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from smr.core.audit import AUDIT_LOG_TABLE, ActorKind, AuditEntry, SqlAlchemyAuditLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_records_an_entry(session: AsyncSession) -> None:
    """An entry is written with its before and after."""
    log = SqlAlchemyAuditLog(session)
    await log.record(
        AuditEntry(
            actor_kind=ActorKind.ADMIN,
            actor_id="42",
            action="grade.changed",
            entity="grade_entry",
            entity_id="7",
            before={"points": 1},
            after={"points": 2},
        ),
    )
    row = (await session.execute(select(AUDIT_LOG_TABLE))).one()
    assert row.action == "grade.changed"
    assert row.before == {"points": 1}
    assert row.after == {"points": 2}


async def test_refuses_to_rewrite_the_log(session: AsyncSession) -> None:
    """An update of the log is refused by the trigger."""
    await SqlAlchemyAuditLog(session).record(
        AuditEntry(ActorKind.SYSTEM, None, "x", "y", "1"),
    )
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(text("UPDATE audit.log SET action = 'z'"))
