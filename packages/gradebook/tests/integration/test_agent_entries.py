"""Ledger entries written by an agent."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from roster_kit import TEACHER
from sqlalchemy import select

from smr.core.audit import AUDIT_LOG_TABLE
from smr.gradebook.domain import WorkTypeKind

if TYPE_CHECKING:
    from gradebook_kit import Gradebook
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_agent_entry_is_audited_as_agent(
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """An agent's points leave graded_by empty and name the model in the audit log."""
    roster = gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    student = next(iter(await roster.api.students_of(group.group_id)))
    types = {t.kind: t for t in await gradebook.scheme(TEACHER, group.group_id)}
    item = await gradebook.create_item(
        TEACHER,
        types[WorkTypeKind.TEST].work_type_id,
        title="БДЗ",
        max_points=Decimal(10),
    )
    entry = await gradebook.ledger.set_entry(
        student.student_id,
        item.item_id,
        Decimal(7),
        excused=False,
        comment=None,
        graded_by=None,
        agent="claude-opus-5-5",
    )
    assert entry.graded_by is None
    rows = (
        await session.execute(
            select(AUDIT_LOG_TABLE).where(AUDIT_LOG_TABLE.c.action == "grade.set"),
        )
    ).all()
    assert rows[-1].actor_kind == "agent"
    assert rows[-1].actor_id == "claude-opus-5-5"


async def test_agent_and_teacher_together_refused(gradebook: Gradebook) -> None:
    """A grade is either the teacher's or the agent's."""
    roster = gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    student = next(iter(await roster.api.students_of(group.group_id)))
    types = {t.kind: t for t in await gradebook.scheme(TEACHER, group.group_id)}
    item = await gradebook.create_item(
        TEACHER,
        types[WorkTypeKind.TEST].work_type_id,
        title="БДЗ",
        max_points=Decimal(10),
    )
    with pytest.raises(ValueError, match="agent"):
        await gradebook.ledger.set_entry(
            student.student_id,
            item.item_id,
            Decimal(7),
            excused=False,
            comment=None,
            graded_by=TEACHER,
            agent="claude-opus-5-5",
        )
