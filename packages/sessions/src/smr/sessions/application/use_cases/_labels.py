"""Ledger titles of attendance items. Points are never touched here."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from smr.core.clock import MOSCOW
from smr.gradebook.application.contracts import GradebookApi
from smr.sessions.application.ports import SessionRepository
from smr.sessions.domain import Session

_ONE = Decimal(1)


def attendance_title(starts_at: datetime, *, with_time: bool) -> str:
    """Name an attendance line.

    Args:
        starts_at: datetime - When the session starts.
        with_time: bool - Add the clock time when the group has another session
            that Moscow day.

    Returns:
        str - ``Занятие dd.mm`` or ``Занятие dd.mm HH:MM``.

    """
    local = starts_at.astimezone(MOSCOW)
    if with_time:
        return f"Занятие {local:%d.%m %H:%M}"
    return f"Занятие {local:%d.%m}"


def moscow_day(starts_at: datetime) -> date:
    """Tell the Moscow calendar day of a session.

    Args:
        starts_at: datetime - When the session starts.

    Returns:
        date - That day in Moscow.

    """
    return starts_at.astimezone(MOSCOW).date()


async def sync_attendance_titles(
    sessions: SessionRepository,
    gradebook: GradebookApi,
    group_id: uuid.UUID,
    *days: date,
) -> None:
    """Rename the attendance items of the given days.

    ``update_item`` rewrites the title and ``counts_from``. It does not rewrite
    grade entries, so the points already given stay as they are.

    Args:
        sessions: SessionRepository - The sessions.
        gradebook: GradebookApi - The ledger.
        group_id: uuid.UUID - The group.
        days: date - Moscow dates whose labels to refresh.

    """
    wanted = set(days)
    if not wanted:
        return
    grouped: dict[date, list[Session]] = {}
    for session in await sessions.of_group(group_id):
        day = moscow_day(session.starts_at)
        if day in wanted:
            grouped.setdefault(day, []).append(session)
    for day_sessions in grouped.values():
        with_time = len(day_sessions) > 1
        for session in day_sessions:
            if session.attendance_item_id is None:
                continue
            _ = await gradebook.update_item(
                session.attendance_item_id,
                title=attendance_title(session.starts_at, with_time=with_time),
                max_points=_ONE,
                counts_from=session.starts_at,
            )
