"""Accepting a new privacy notice."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER
from sqlalchemy import select

from smr.core.audit import AUDIT_LOG_TABLE
from smr.roster.domain import CONSENT_VERSION, Group, Student

if TYPE_CHECKING:
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _group(roster: Roster, title: str) -> tuple[Group, Student]:
    group = await roster.create(
        TEACHER,
        title=title,
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    student = next(iter(await roster.api.students_of(group.group_id)))
    return group, student


async def test_old_consent_is_not_current(roster: Roster) -> None:
    """A claim under the old notice is not the current one."""
    group, student = await _group(roster, "К01-261")
    _ = await roster.claim(group.invite_code, student.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, student.student_id)
    assert await roster.api.consented(student.student_id) is False


async def test_accepting_updates_every_bound_row(
    roster: Roster,
    session: AsyncSession,
) -> None:
    """One acceptance covers every group the account holds, and each row is audited."""
    first_group, first = await _group(roster, "К01-261")
    second_group, second = await _group(roster, "К02-261")
    _ = await roster.claim(first_group.invite_code, first.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, first.student_id)
    _ = await roster.claim(second_group.invite_code, second.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, second.student_id)
    assert await roster.accept(STUDENT) == 2
    assert await roster.api.consented(first.student_id) is True
    assert await roster.api.consented(second.student_id) is True
    rows = (
        await session.execute(
            select(AUDIT_LOG_TABLE).where(AUDIT_LOG_TABLE.c.action == "roster.consent"),
        )
    ).all()
    assert len(rows) == 2
    assert {row.actor_kind for row in rows} == {"student"}
    assert all(row.after == {"version": CONSENT_VERSION} for row in rows)
