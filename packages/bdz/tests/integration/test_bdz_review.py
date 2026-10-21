"""A БДЗ the review can see, until the group is archived."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from roster_kit import STUDENT, TEACHER
from sqlalchemy import select

from smr.bdz.application.use_cases import BdzDraft, Upload
from smr.core.audit import AUDIT_LOG_TABLE
from smr.gradebook.domain import WorkTypeKind
from smr.gradebook.infrastructure.models import EntryModel
from smr.review.application.use_cases import TaskInput, VerdictInput
from smr.review.domain import AlreadyReviewedError, SchemeTask, StaleWorkError
from smr.review.infrastructure.models import AppealModel, VerdictModel

if TYPE_CHECKING:
    from datetime import datetime

    from bdz_kit import BdzBox
    from gradebook_kit import Gradebook
    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.bdz.domain import Bdz, BdzSubmission

pytestmark = pytest.mark.integration


def _upload(data: bytes, sent_at: datetime) -> Upload:
    return Upload(data, "tg", "uniq", sent_at)


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def test_archived_group_hides_works(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """An archived group's work leaves the queue and refuses a verdict."""
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
    _ = await roster.accept(STUDENT)
    types = {
        item.kind: item for item in await gradebook.scheme(TEACHER, group.group_id)
    }
    now = roster.clock.now()
    pdf = _pdf()
    created: Bdz = await bdz.create(
        TEACHER,
        group.group_id,
        BdzDraft(
            "Контрольная",
            now + timedelta(days=2),
            types[WorkTypeKind.TEST].work_type_id,
            (SchemeTask(1, Decimal(10)),),
        ),
        _upload(pdf, now),
        Upload(pdf, "tg-s", "uniq-s", now),
    )
    sent = await bdz.send(STUDENT, created.bdz_id, _upload(pdf, now))
    await roster.archive(TEACHER, group.group_id)
    assert await bdz.pending() == []
    with pytest.raises(StaleWorkError):
        await bdz.submit(
            VerdictInput(
                f"bdz:{sent.submission_id}",
                sent.sha256,
                "m",
                "",
                (1,),
                (
                    TaskInput(
                        1,
                        Decimal(7),
                        "Верно.",
                        unreadable=False,
                        unsure=False,
                        manipulation=False,
                        pages=(1,),
                    ),
                ),
            ),
        )


async def test_grade_appeal_and_teacher_final(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    notifications: Notifications,
    session: AsyncSession,
) -> None:
    """A published grade can be appealed, and the teacher can lower it."""
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
    _ = await roster.accept(STUDENT)
    types = {
        item.kind: item for item in await gradebook.scheme(TEACHER, group.group_id)
    }
    now = roster.clock.now()
    pdf = _pdf()
    created: Bdz = await bdz.create(
        TEACHER,
        group.group_id,
        BdzDraft(
            "Контрольная",
            now + timedelta(days=2),
            types[WorkTypeKind.TEST].work_type_id,
            (SchemeTask(1, Decimal(10)),),
        ),
        _upload(pdf, now),
        Upload(pdf, "tg-s", "uniq-s", now),
    )
    sent = await bdz.send(STUDENT, created.bdz_id, _upload(pdf, now))
    pending = await bdz.pending()
    assert [item.work_ref for item in pending] == [f"bdz:{sent.submission_id}"]
    _ = await bdz.submit(
        VerdictInput(
            f"bdz:{sent.submission_id}",
            sent.sha256,
            "m",
            "",
            (1,),
            (
                TaskInput(
                    1,
                    Decimal(7),
                    "Верно.",
                    unreadable=False,
                    unsure=False,
                    manipulation=False,
                    pages=(1,),
                ),
            ),
        ),
    )
    verdict_id = await session.scalar(
        select(VerdictModel.verdict_id).where(
            VerdictModel.work_id == sent.submission_id,
        ),
    )
    assert verdict_id is not None
    entry = await session.scalar(
        select(EntryModel).where(EntryModel.item_id == created.item_id),
    )
    assert entry is not None
    assert entry.points == Decimal(7)
    kinds = [item.kind for item in await notifications.queued()]
    assert "review_published" in kinds
    _ = await bdz.appeal(
        STUDENT,
        "bdz",
        sent.submission_id,
        "Не согласен с баллом за задачу.",
    )
    final = await bdz.finalize(TEACHER, verdict_id, {1: Decimal(5)}, {}, "")
    await session.refresh(entry)
    assert entry.points == Decimal(5)
    kinds = [item.kind for item in await notifications.queued()]
    assert "review_final" in kinds
    appeal = await session.scalar(
        select(AppealModel).where(AppealModel.verdict_id == verdict_id),
    )
    assert appeal is not None
    assert appeal.status == "resolved"
    assert appeal.resolution_verdict_id == final.verdict_id
    actions = await session.scalars(select(AUDIT_LOG_TABLE.c.action))
    assert {"review.published", "review.appealed", "review.finalized"} <= set(actions)


async def _handed_in(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> tuple[Bdz, BdzSubmission]:
    """Publish one task and accept one PDF.

    Returns:
        tuple[Bdz, BdzSubmission] - The assignment and the live version.

    """
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
    _ = await roster.accept(STUDENT)
    types = {
        item.kind: item for item in await gradebook.scheme(TEACHER, group.group_id)
    }
    now = roster.clock.now()
    pdf = _pdf()
    created = await bdz.create(
        TEACHER,
        group.group_id,
        BdzDraft(
            "Контрольная",
            now + timedelta(days=2),
            types[WorkTypeKind.TEST].work_type_id,
            (SchemeTask(1, Decimal(10)),),
        ),
        _upload(pdf, now),
        Upload(pdf, "tg-s", "uniq-s", now),
    )
    sent = await bdz.send(STUDENT, created.bdz_id, _upload(pdf, now))
    return created, sent


def _verdict(
    sent: BdzSubmission,
    *,
    points: Decimal | None = None,
    sha256: str | None = None,
    unreadable: bool = False,
    manipulation: bool = False,
) -> VerdictInput:
    score = Decimal(7) if points is None else points
    return VerdictInput(
        f"bdz:{sent.submission_id}",
        sha256 or sent.sha256,
        "m",
        "",
        (1,),
        (
            TaskInput(
                1,
                score,
                "Верно.",
                unreadable=unreadable,
                unsure=False,
                manipulation=manipulation,
                pages=(1,),
            ),
        ),
    )


async def test_unreadable_page_writes_no_grade(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    notifications: Notifications,
    session: AsyncSession,
) -> None:
    """An unreadable page waits for the teacher and skips the ledger."""
    created, sent = await _handed_in(bdz, roster, gradebook)
    outcome = await bdz.submit(_verdict(sent, points=Decimal(0), unreadable=True))
    assert outcome.status == "manual"
    entry = await session.scalar(
        select(EntryModel).where(EntryModel.item_id == created.item_id),
    )
    assert entry is None
    kinds = [item.kind for item in await notifications.queued()]
    assert "review_manual" in kinds


async def test_stale_file_is_refused(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A verdict about another file is refused."""
    _, sent = await _handed_in(bdz, roster, gradebook)
    with pytest.raises(StaleWorkError):
        await bdz.submit(_verdict(sent, sha256="ab" * 32))


async def test_second_verdict_is_refused(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A live version is graded once."""
    _, sent = await _handed_in(bdz, roster, gradebook)
    _ = await bdz.submit(_verdict(sent))
    with pytest.raises(AlreadyReviewedError):
        await bdz.submit(_verdict(sent, points=Decimal(8)))


async def test_manipulation_is_audited(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """A task that addresses the grader scores zero and is audited."""
    _, sent = await _handed_in(bdz, roster, gradebook)
    outcome = await bdz.submit(
        _verdict(sent, points=Decimal(0), manipulation=True),
    )
    assert outcome.status == "published"
    assert outcome.total == Decimal(0)
    actions = await session.scalars(select(AUDIT_LOG_TABLE.c.action))
    assert "review.manipulation" in set(actions)


async def test_pending_work_carries_the_journal_number(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """The agent gets the student's journal number, never the name."""
    _, sent = await _handed_in(bdz, roster, gradebook)
    await roster.journal(TEACHER, sent.student_id, 17)
    pending = await bdz.pending()
    assert [work.journal_no for work in pending] == [17]
    assert "Иванов" not in repr(pending)
