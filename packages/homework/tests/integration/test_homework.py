"""Homework over a real database and a temporary disk."""

from __future__ import annotations

import zipfile
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from homework_kit import MAX_FILES
from roster_kit import STUDENT, TEACHER

from smr.core.files import UnsupportedFileError
from smr.homework.application.use_cases import AssignmentDraft, Upload
from smr.homework.domain import (
    DraftEmptyError,
    NotYourAssignmentError,
    SubmissionClosedError,
    SubmissionStatus,
    TooManyFilesError,
)

if TYPE_CHECKING:
    from datetime import datetime

    from homework_kit import Homework

    from smr.homework.domain import Assignment
    from smr.roster.domain import Group, Student

pytestmark = pytest.mark.integration

PDF = b"%PDF-1.7\n"
JPEG = b"\xff\xd8\xff\xe0 photo"


def _upload(data: bytes, sent_at: datetime, n: int = 1) -> Upload:
    return Upload(data, f"file-{n}", f"unique-{n}", sent_at)


async def _setup(homework: Homework) -> tuple[Group, Student, Assignment]:
    roster = homework.gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов Иван\nПетров Пётр")
    _ = await homework.gradebook.scheme(TEACHER, group.group_id)
    ivanov = (await roster.api.students_of(group.group_id))[0]
    _ = await roster.claim(group.invite_code, ivanov.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, ivanov.student_id)
    deadline = roster.clock.now() + timedelta(days=3)
    assignment = await homework.create(
        TEACHER,
        group.group_id,
        AssignmentDraft("ДЗ 3", "Задания 1–6", deadline, Decimal(3)),
        statement=_upload(PDF, roster.clock.now()),
    )
    return group, ivanov, assignment


async def test_draft_submit_grade(homework: Homework) -> None:
    """Files gather in a draft, are submitted on time, graded, and the total moves."""
    group, ivanov, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    assert (
        await homework.add_file(
            STUDENT,
            assignment.assignment_id,
            _upload(JPEG, now, 1),
        )
        == 1
    )
    assert (
        await homework.add_file(STUDENT, assignment.assignment_id, _upload(PDF, now, 2))
        == 2
    )
    submitted = await homework.submit(STUDENT, assignment.assignment_id)
    assert submitted.status is SubmissionStatus.SUBMITTED
    assert not submitted.is_late
    queue = await homework.queue(TEACHER, group.group_id)
    assert [s.submission_id for s in queue] == [submitted.submission_id]
    review = await homework.open(TEACHER, submitted.submission_id)
    assert [f.position for f in review.files] == [1, 2]
    graded, author = await homework.grade(
        TEACHER,
        submitted.submission_id,
        Decimal(3),
        "отлично",
    )
    assert graded.status is SubmissionStatus.GRADED
    assert author.student_id == ivanov.student_id
    work = await homework.work(STUDENT, assignment.assignment_id)
    assert (work.points, work.comment) == (Decimal(3), "отлично")
    rows = await homework.gradebook.sheet(TEACHER, group.group_id)
    totals = {r.student.full_name: r.score.total for r in rows}
    assert totals["Иванов Иван"] == Decimal(12)
    assert await homework.queue(TEACHER, group.group_id) == []


async def test_late_by_telegram_clock(homework: Homework) -> None:
    """A file sent after the deadline makes the work late, whenever it is processed."""
    _, _, assignment = await _setup(homework)
    after = assignment.deadline + timedelta(minutes=1)
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(JPEG, after))
    assert (await homework.submit(STUDENT, assignment.assignment_id)).is_late


async def test_resubmission_supersedes_and_deletes_old_files(
    homework: Homework,
) -> None:
    """A second submit replaces the first and removes its files from disk."""
    _, ivanov, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    _ = await homework.add_file(
        STUDENT,
        assignment.assignment_id,
        _upload(JPEG, now, 1),
    )
    first = await homework.submit(STUDENT, assignment.assignment_id)
    old_files = (await homework.open(TEACHER, first.submission_id)).files
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(PDF, now, 2))
    second = await homework.submit(STUDENT, assignment.assignment_id)
    assert second.version == 2
    assert all(not homework.files.path(f.path).exists() for f in old_files)
    live = [
        s for _, s in await homework.roster_view(TEACHER, assignment.assignment_id) if s
    ]
    assert [s.submission_id for s in live] == [second.submission_id]
    _ = ivanov


async def test_graded_work_is_closed(homework: Homework) -> None:
    """After grading the student cannot add files or resubmit."""
    _, _, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(JPEG, now))
    submitted = await homework.submit(STUDENT, assignment.assignment_id)
    _ = await homework.grade(TEACHER, submitted.submission_id, Decimal(2), None)
    with pytest.raises(SubmissionClosedError):
        await homework.add_file(STUDENT, assignment.assignment_id, _upload(PDF, now))


async def test_limits_and_types(homework: Homework) -> None:
    """An executable is refused; so is a file beyond the limit; an empty draft cannot be sent."""
    _, _, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    with pytest.raises(DraftEmptyError):
        await homework.submit(STUDENT, assignment.assignment_id)
    with pytest.raises(UnsupportedFileError):
        await homework.add_file(
            STUDENT,
            assignment.assignment_id,
            _upload(b"MZ\x90\x00", now),
        )
    for n in range(MAX_FILES):
        _ = await homework.add_file(
            STUDENT,
            assignment.assignment_id,
            _upload(JPEG, now, n),
        )
    with pytest.raises(TooManyFilesError):
        await homework.add_file(
            STUDENT,
            assignment.assignment_id,
            _upload(JPEG, now, 99),
        )


async def test_stranger_cannot_submit(homework: Homework) -> None:
    """An account without an approved row of the group is refused."""
    _, _, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    with pytest.raises(NotYourAssignmentError):
        await homework.add_file(
            STUDENT + 1,
            assignment.assignment_id,
            _upload(JPEG, now),
        )


async def test_clearing_a_draft_removes_its_files(homework: Homework) -> None:
    """A thrown-away draft leaves nothing on disk."""
    _, _, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(JPEG, now))
    await homework.clear(STUDENT, assignment.assignment_id)
    work = await homework.work(STUDENT, assignment.assignment_id)
    assert work.draft_files == 0
    stored = [p for p in (homework.data_dir / "files").rglob("*") if p.is_file()]
    assert len(stored) == 1  # only the statement


async def test_forget_deletes_the_students_files(homework: Homework) -> None:
    """Forgetting a student removes every file they sent."""
    _, ivanov, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(JPEG, now))
    _ = await homework.submit(STUDENT, assignment.assignment_id)
    assert await homework.forget_files([ivanov.student_id]) == 1


async def test_deadline_change_moves_the_ledger_item(homework: Homework) -> None:
    """Moving the deadline earlier makes a missing work count against the student."""
    group, _, assignment = await _setup(homework)
    roster = homework.gradebook.roster
    rows = {
        r.student.full_name: r
        for r in await homework.gradebook.sheet(TEACHER, group.group_id)
    }
    assert not rows["Петров Пётр"].score.parts[1].counted
    _ = await homework.update(
        TEACHER,
        assignment.assignment_id,
        AssignmentDraft(
            assignment.title,
            assignment.body,
            roster.clock.now() - timedelta(hours=1),
            Decimal(3),
        ),
    )
    rows = {
        r.student.full_name: r
        for r in await homework.gradebook.sheet(TEACHER, group.group_id)
    }
    assert rows["Петров Пётр"].score.parts[1].counted


async def test_export_has_a_folder_per_student(homework: Homework) -> None:
    """The export zip holds each student's files under their name."""
    _, _, assignment = await _setup(homework)
    now = homework.gradebook.roster.clock.now()
    _ = await homework.add_file(STUDENT, assignment.assignment_id, _upload(JPEG, now))
    _ = await homework.submit(STUDENT, assignment.assignment_id)
    target = await homework.export(TEACHER, assignment.assignment_id)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["Иванов Иван/01.jpg"]


async def test_copy_to_another_group(homework: Homework) -> None:
    """A copy is an independent assignment of the other group with its own deadline."""
    _, _, assignment = await _setup(homework)
    roster = homework.gradebook.roster
    other = await roster.create(
        TEACHER,
        title="К01-262",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await homework.gradebook.scheme(TEACHER, other.group_id)
    later = assignment.deadline + timedelta(days=1)
    copy = await homework.copy(TEACHER, assignment.assignment_id, other.group_id, later)
    assert (copy.group_id, copy.deadline) == (other.group_id, later)
    assert copy.statement is not None
    assert assignment.statement is not None
    assert copy.statement.path != assignment.statement.path
