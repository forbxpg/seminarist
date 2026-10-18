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
from smr.review.domain import SchemeTask, StaleWorkError
from smr.review.infrastructure.models import AppealModel, VerdictModel

if TYPE_CHECKING:
    from datetime import datetime

    from bdz_kit import BdzBox
    from gradebook_kit import Gradebook
    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.bdz.domain import Bdz

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
