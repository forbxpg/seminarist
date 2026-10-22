"""Ordinary homework offered to the review agent."""

from __future__ import annotations

import hashlib
import zipfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from operator import attrgetter
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from roster_kit import STUDENT, TEACHER

from smr.homework.application.services import HomeworkReviewSource
from smr.homework.application.use_cases import AssignmentDraft, Upload
from smr.homework.domain import SubmissionStatus
from smr.homework.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemyFiles,
    SqlAlchemySubmissions,
)
from smr.review.application.services import Reviews
from smr.review.application.use_cases import PendingWorks
from smr.review.domain import VerdictStatus
from smr.review.infrastructure.repositories import (
    SqlAlchemyAppeals,
    SqlAlchemyVerdicts,
)

if TYPE_CHECKING:
    from datetime import datetime

    from homework_kit import Homework
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.homework.domain import Assignment
    from smr.roster.domain import Group, Student

pytestmark = pytest.mark.integration

JPEG = b"\xff\xd8\xff\xe0 photo"


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _docx() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def _upload(data: bytes, sent_at: datetime, n: int) -> Upload:
    return Upload(data, f"file-{n}", f"unique-{n}", sent_at)


async def _group(homework: Homework) -> tuple[Group, Student]:
    roster = homework.gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов Иван")
    _ = await homework.gradebook.scheme(TEACHER, group.group_id)
    ivanov = (await roster.api.students_of(group.group_id))[0]
    _ = await roster.claim(group.invite_code, ivanov.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, ivanov.student_id)
    _ = await roster.journal(TEACHER, ivanov.student_id, 7)
    return group, ivanov


def _wire(
    homework: Homework,
    session: AsyncSession,
) -> tuple[HomeworkReviewSource, PendingWorks, Reviews]:
    verdicts = SqlAlchemyVerdicts(session)
    source = HomeworkReviewSource(
        SqlAlchemyAssignments(session),
        SqlAlchemySubmissions(session),
        SqlAlchemyFiles(session),
        homework.gradebook.roster.api,
        homework.gradebook.ledger,
        homework.files,
    )
    pending = PendingWorks((source,), verdicts)
    reviews = Reviews(verdicts, SqlAlchemyAppeals(session))
    return source, pending, reviews


async def _assignment(
    homework: Homework,
    group: Group,
    title: str,
    *,
    statement: Upload | None = None,
) -> Assignment:
    deadline = homework.gradebook.roster.clock.now() + timedelta(days=3)
    return await homework.create(
        TEACHER,
        group.group_id,
        AssignmentDraft(title, "Задания 1–6", deadline, Decimal(3)),
        statement=statement,
    )


async def test_photos_and_pdf_wait_for_the_homework_queue(
    homework: Homework,
    session: AsyncSession,
) -> None:
    """A photo plus a PDF is one work, and the default queue does not take it."""
    group, _student = await _group(homework)
    now = homework.gradebook.roster.clock.now()
    assignment = await _assignment(homework, group, "ДЗ 3")
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        _upload(JPEG, now, 1),
    )
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        _upload(_pdf(), now, 2),
    )
    submitted = await homework.submit(STUDENT, assignment.assignment_id)
    source, pending, _ = _wire(homework, session)

    assert await pending() == []
    found = await pending("homework")
    assert [item.work_ref for item in found] == [
        f"homework:{submitted.submission_id}",
    ]
    assert found[0].pages == 2
    assert found[0].journal_no == 7

    work = await source.work(submitted.submission_id)
    assert work is not None
    files = sorted(
        await SqlAlchemyFiles(session).of_submission(submitted.submission_id),
        key=attrgetter("position"),
    )
    digest = hashlib.sha256(
        "\n".join(file.sha256 for file in files).encode(),
    ).hexdigest()
    assert work.sha256 == digest
    assert [
        (page.kind, page.pdf_pages)
        for page in await source.pages(submitted.submission_id)
    ] == [
        ("image", 1),
        ("pdf", 1),
    ]

    await source.apply_grade(
        submitted.submission_id,
        Decimal(2),
        teacher=TEACHER,
        agent=None,
    )
    graded = await SqlAlchemySubmissions(session).get(submitted.submission_id)
    assert graded is not None
    assert graded.status is SubmissionStatus.GRADED
    assert graded.entry_id is not None
    entry = await homework.gradebook.ledger.entry(graded.entry_id)
    assert entry is not None
    assert entry.points == Decimal(2)
    assert await pending("homework") == []
    assert await source.work(submitted.submission_id) is not None


async def test_statement_is_text_unless_it_is_a_pdf(
    homework: Homework,
    session: AsyncSession,
) -> None:
    """A written statement is a note. A PDF statement is counted and rendered."""
    group, _student = await _group(homework)
    now = homework.gradebook.roster.clock.now()
    written = await _assignment(homework, group, "ДЗ 3")
    stated = await _assignment(
        homework,
        group,
        "ДЗ с файлом",
        statement=_upload(_pdf(), now, 9),
    )
    source, _pending, _reviews = _wire(homework, session)
    written_sheet = await source.sheet(written.assignment_id)
    stated_sheet = await source.sheet(stated.assignment_id)
    assert written_sheet.note == "Задания 1–6"
    assert written_sheet.statement_pages == 0
    assert written_sheet.solutions_path is None
    assert len(written_sheet.scheme) == 1
    assert written_sheet.scheme[0].max_points == Decimal(3)
    assert stated_sheet.statement_pages == 1
    assert not stated_sheet.note


async def test_docx_goes_to_the_teacher_and_skips_the_agent(
    homework: Homework,
    session: AsyncSession,
) -> None:
    """A DOCX cannot be read, so it is flagged and never offered to the agent."""
    group, _student = await _group(homework)
    now = homework.gradebook.roster.clock.now()
    assignment = await _assignment(homework, group, "ДЗ 4")
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        _upload(_docx(), now, 1),
    )
    submitted = await homework.submit(STUDENT, assignment.assignment_id)
    _, pending, reviews = _wire(homework, session)
    verdict = await reviews.current("homework", submitted.submission_id)
    assert verdict is not None
    assert verdict.status is VerdictStatus.MANUAL
    assert verdict.total == Decimal(0)
    assert verdict.grader == "system"
    assert verdict.tasks[0].unreadable
    assert "DOCX" in verdict.summary
    assert await pending() == []
    assert await pending("homework") == []
