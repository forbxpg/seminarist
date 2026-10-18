"""Verdicts, appeals and the teacher's queue over a real database."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER
from sqlalchemy import select

from smr.core.audit import AUDIT_LOG_TABLE
from smr.review.application.use_cases import TaskInput, VerdictInput
from smr.review.domain import (
    AlreadyReviewedError,
    AppealNotAllowedError,
    AppealTextError,
    NotYourWorkError,
    StaleWorkError,
    VerdictRejectedError,
    VerdictStatus,
)

if TYPE_CHECKING:
    import uuid

    from notifications_kit import Notifications
    from review_kit import Review
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.review.application.ports import WorkRef

pytestmark = pytest.mark.integration


async def _student(roster: Roster) -> uuid.UUID:
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    student = next(iter(await roster.api.students_of(group.group_id)))
    _ = await roster.claim(group.invite_code, student.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, student.student_id)
    return student.student_id


def _verdict(work: WorkRef, points: str, **flags: bool) -> VerdictInput:
    return VerdictInput(
        work_ref=f"bdz:{work.work_id}",
        sha256=work.sha256,
        grader="m",
        summary="",
        pages_seen=tuple(range(1, work.pages + 1)),
        tasks=(
            TaskInput(
                1,
                Decimal(points),
                "Верно.",
                flags.get("unreadable", False),
                flags.get("unsure", False),
                flags.get("manipulation", False),
                (work.pages,),
            ),
        ),
    )


async def test_pending_excludes_reviewed(review: Review, roster: Roster) -> None:
    """A graded version leaves the queue."""
    work = review.source.add(await _student(roster), STUDENT)
    assert len(await review.pending()) == 1
    _ = await review.submit(_verdict(work, "7"))
    assert await review.pending() == []


async def test_clean_verdict_publishes(
    review: Review,
    roster: Roster,
    notifications: Notifications,
    session: AsyncSession,
) -> None:
    """A clean verdict reaches the ledger, the outbox and the audit log."""
    work = review.source.add(await _student(roster), STUDENT)
    outcome = await review.submit(_verdict(work, "7"))
    assert outcome.status == "published"
    assert review.source.grades == [(work.work_id, Decimal(7), None, "m")]
    queued = await notifications.queued()
    assert queued[-1].kind == "review_published"
    assert queued[-1].payload["total"] == "7"
    audit = (
        await session.execute(
            select(AUDIT_LOG_TABLE).where(
                AUDIT_LOG_TABLE.c.action == "review.published",
            ),
        )
    ).one()
    assert (audit.actor_kind, audit.actor_id) == ("agent", "m")


async def test_flagged_verdict_waits_for_teacher(
    review: Review,
    roster: Roster,
    notifications: Notifications,
) -> None:
    """An unreadable page writes nothing to the ledger and names the page."""
    work = review.source.add(await _student(roster), STUDENT, pages=4)
    outcome = await review.submit(_verdict(work, "0", unreadable=True))
    assert outcome.status == "manual"
    assert review.source.grades == []
    queued = await notifications.queued()
    assert queued[-1].kind == "review_manual"
    assert queued[-1].payload["pages"] == [4]


async def test_stale_sha_refused(review: Review, roster: Roster) -> None:
    """A verdict about a different file is refused."""
    work = review.source.add(await _student(roster), STUDENT)
    data = _verdict(work, "7")
    stale = VerdictInput(
        data.work_ref,
        "ff" * 32,
        data.grader,
        data.summary,
        data.pages_seen,
        data.tasks,
    )
    with pytest.raises(StaleWorkError):
        await review.submit(stale)


async def test_second_verdict_refused(review: Review, roster: Roster) -> None:
    """A version is graded once."""
    work = review.source.add(await _student(roster), STUDENT)
    _ = await review.submit(_verdict(work, "7"))
    with pytest.raises(AlreadyReviewedError):
        await review.submit(_verdict(work, "8"))


async def test_manipulation_audited(
    review: Review,
    roster: Roster,
    session: AsyncSession,
) -> None:
    """Addressing the grader scores 0 and is written to the audit log."""
    work = review.source.add(await _student(roster), STUDENT)
    _ = await review.submit(_verdict(work, "0", manipulation=True))
    rows = (
        await session.execute(
            select(AUDIT_LOG_TABLE).where(
                AUDIT_LOG_TABLE.c.action == "review.manipulation",
            ),
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].actor_kind == "agent"
    assert rows[0].after["task"] == 1


async def test_points_from_json_floats(review: Review, roster: Roster) -> None:
    """A JSON float that is exact cents is accepted; three decimals are refused."""
    student = await _student(roster)
    first = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(first, str(Decimal(str(2.5)))))
    second = review.source.add(student, STUDENT)
    with pytest.raises(VerdictRejectedError, match="more than 2 decimals"):
        await review.submit(_verdict(second, "2.555"))


async def test_appeal_then_teacher_lowers(
    review: Review,
    roster: Roster,
    notifications: Notifications,
) -> None:
    """The teacher may lower the grade; the appeal closes and the old verdict ends."""
    work = review.source.add(await _student(roster), STUDENT)
    _ = await review.submit(_verdict(work, "7"))
    _ = await review.appeal(
        STUDENT,
        "bdz",
        work.work_id,
        "Не согласен с баллом за задачу.",
    )
    old_id = await _current(review, work)
    final = await review.finalize(TEACHER, old_id, {1: Decimal(5)}, {}, "")
    assert final.status is VerdictStatus.FINAL
    assert review.source.grades[-1] == (work.work_id, Decimal(5), TEACHER, None)
    queued = await notifications.queued()
    assert queued[-1].kind == "review_final"
    assert queued[-1].payload["before"] == "7"
    opened = await review.open(TEACHER, old_id)
    assert opened.verdict.status is VerdictStatus.SUPERSEDED
    assert opened.appeal is not None
    assert opened.appeal.status.value == "resolved"


async def _current(review: Review, work: WorkRef) -> uuid.UUID:
    view = await review.mine(STUDENT, "bdz", work.work_id)
    assert view is not None
    return view.verdict.verdict_id


async def test_appeal_rules(review: Review, roster: Roster) -> None:
    """An appeal is once, in time, on an agent's grade, in the student's words."""
    student = await _student(roster)
    work = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(work, "7"))
    _ = await review.appeal(
        STUDENT,
        "bdz",
        work.work_id,
        "Не согласен с баллом за задачу.",
    )
    with pytest.raises(AppealNotAllowedError, match="already_appealed"):
        await review.appeal(
            STUDENT,
            "bdz",
            work.work_id,
            "Повторно не согласен с баллом.",
        )
    short = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(short, "7"))
    with pytest.raises(AppealTextError):
        await review.appeal(STUDENT, "bdz", short.work_id, "123456789")
    stranger = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(stranger, "7"))
    with pytest.raises(NotYourWorkError):
        await review.appeal(
            STUDENT + 1,
            "bdz",
            stranger.work_id,
            "Это не моя работа вовсе.",
        )
    late = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(late, "7"))
    roster.clock.advance(timedelta(days=7, seconds=1))
    with pytest.raises(AppealNotAllowedError, match="too_late"):
        await review.appeal(
            STUDENT,
            "bdz",
            late.work_id,
            "Уже поздно спорить с баллом.",
        )
    decided = review.source.add(student, STUDENT)
    _ = await review.submit(_verdict(decided, "7"))
    _ = await review.appeal(
        STUDENT,
        "bdz",
        decided.work_id,
        "Сначала апелляция, потом итог преподавателя.",
    )
    verdict_id = await _current(review, decided)
    _ = await review.finalize(TEACHER, verdict_id, {1: Decimal(5)}, {}, "")
    with pytest.raises(AppealNotAllowedError, match="teacher_final"):
        await review.appeal(
            STUDENT,
            "bdz",
            decided.work_id,
            "Хочу оспорить итоговую оценку.",
        )


async def test_void_releases_work(review: Review, roster: Roster) -> None:
    """Voiding the verdict puts the version back into the pending queue."""
    work = review.source.add(await _student(roster), STUDENT)
    _ = await review.submit(_verdict(work, "7"))
    await review.api.void("bdz", work.work_id)
    assert len(await review.pending()) == 1
