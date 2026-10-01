"""What homework tells students, and the deadline reminders."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER

from smr.homework.application.use_cases import AssignmentDraft, Upload

if TYPE_CHECKING:
    from homework_kit import Homework

    from smr.homework.domain import Assignment

pytestmark = pytest.mark.integration


async def _assignment(homework: Homework, deadline: datetime) -> Assignment:
    roster = homework.gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов\nПетров")
    _ = await homework.gradebook.scheme(TEACHER, group.group_id)
    ivanov, petrov = await roster.api.students_of(group.group_id)
    for tg, row in ((STUDENT, ivanov), (STUDENT + 1, petrov)):
        _ = await roster.claim(group.invite_code, row.student_id, tg, "v1")
        _ = await roster.approve(TEACHER, row.student_id)
    return await homework.create(
        TEACHER,
        group.group_id,
        AssignmentDraft("ДЗ 3", "", deadline, Decimal(3)),
    )


async def _kinds(homework: Homework) -> list[tuple[int, str]]:
    return [(row.tg_user_id, row.kind) for row in await homework.notifications.queued()]


async def test_new_assignment_and_grade_are_told(homework: Homework) -> None:
    """The group hears of the assignment; the author hears of the grade."""
    now = homework.gradebook.roster.clock.now()
    assignment = await _assignment(homework, now + timedelta(days=3))
    assert await _kinds(homework) == [
        (STUDENT, "assignment_published"),
        (STUDENT + 1, "assignment_published"),
    ]
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        Upload(b"%PDF-1.7\n", "f", "u", now),
    )
    submitted = await homework.submit(STUDENT, assignment.assignment_id)
    _ = await homework.grade(TEACHER, submitted.submission_id, Decimal("2.5"), "почти")
    graded = (await homework.notifications.queued())[-1]
    assert (graded.tg_user_id, graded.kind) == (STUDENT, "homework_graded")
    assert graded.payload == {
        "title": "ДЗ 3",
        "points": "2.5",
        "max_points": "3",
        "comment": "почти",
    }


async def test_reminders_go_once_to_those_who_have_not_submitted(
    homework: Homework,
) -> None:
    """Inside the window, students without a submission are reminded once; muted ones never."""
    clock = homework.gradebook.roster.clock
    now = clock.now()
    assignment = await _assignment(homework, now + timedelta(hours=30))
    assert await homework.reminders() == 0  # 30 hours ahead: outside the 24-hour window
    clock.advance(timedelta(hours=7))
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        Upload(b"%PDF-1.7\n", "f", "u", clock.now()),
    )
    _ = await homework.submit(STUDENT, assignment.assignment_id)
    assert await homework.reminders() == 1
    assert await homework.reminders() == 0
    reminders = [
        tg for tg, kind in await _kinds(homework) if kind == "deadline_reminder"
    ]
    assert reminders == [STUDENT + 1]


async def test_muted_students_are_not_reminded(homework: Homework) -> None:
    """A student with reminders off gets none."""
    clock = homework.gradebook.roster.clock
    _ = await _assignment(homework, clock.now() + timedelta(hours=2))
    await homework.notifications.set_reminders(STUDENT, enabled=False)
    assert await homework.reminders() == 1
