"""Publishing a БДЗ and sending a PDF."""

from __future__ import annotations

import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from roster_kit import STUDENT, TEACHER
from sqlalchemy import select

from smr.bdz.application.use_cases import BdzDraft, Upload
from smr.bdz.domain import (
    ConsentRequiredError,
    NotAPdfError,
    TooManyPagesError,
    WorkTypeNotProportionalError,
)
from smr.core.files import PdfLockedError
from smr.gradebook.domain import WorkTypeKind
from smr.gradebook.infrastructure.models import EntryModel
from smr.review.application.use_cases import TaskInput, VerdictInput
from smr.review.domain import AppealOpenError, SchemeTask, VerdictStatus
from smr.review.infrastructure.models import VerdictModel

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

    from bdz_kit import BdzBox
    from gradebook_kit import Gradebook
    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.bdz.domain import Bdz, BdzSubmission
    from smr.gradebook.domain import WorkType
    from smr.roster.domain import Group, Student

pytestmark = pytest.mark.integration


def _pdf(pages: int, *, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if password is not None:
        writer.encrypt(password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _upload(data: bytes, sent_at: datetime, name: str) -> Upload:
    return Upload(data, f"tg-{name}", f"uniq-{name}", sent_at)


async def _ready(
    roster: Roster,
    gradebook: Gradebook,
) -> tuple[Group, Student, WorkType]:
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
    return group, student, types[WorkTypeKind.TEST]


def _draft(when: datetime, work_type_id: uuid.UUID, *, hours: int = 48) -> BdzDraft:
    return BdzDraft(
        "Контрольная",
        when + timedelta(hours=hours),
        work_type_id,
        (SchemeTask(1, Decimal(10)),),
    )


async def _publish(
    box: BdzBox,
    roster: Roster,
    group: Group,
    work_type_id: uuid.UUID,
    *,
    hours: int = 48,
) -> Bdz:
    now = roster.clock.now()
    return await box.create(
        TEACHER,
        group.group_id,
        _draft(now, work_type_id, hours=hours),
        _upload(_pdf(1), now, "statement"),
        _upload(_pdf(1), now, "solutions"),
    )


def _grade(submission: BdzSubmission) -> VerdictInput:
    return VerdictInput(
        work_ref=f"bdz:{submission.submission_id}",
        sha256=submission.sha256,
        grader="m",
        summary="",
        pages_seen=tuple(range(1, submission.pages + 1)),
        tasks=(
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
    )


async def test_create_issues_item_and_notifies(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    notifications: Notifications,
) -> None:
    """Publishing issues a ledger item and tells the group."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    assert created.item_id is not None
    assert created.max_points == Decimal(10)
    assert (await notifications.queued())[-1].kind == "bdz_published"


async def test_accumulating_work_type_refused(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """An accumulating work type cannot hold a БДЗ."""
    group, _, _ = await _ready(roster, gradebook)
    types = {
        item.kind: item for item in await gradebook.ledger.work_types(group.group_id)
    }
    now = roster.clock.now()
    with pytest.raises(WorkTypeNotProportionalError):
        await bdz.create(
            TEACHER,
            group.group_id,
            _draft(now, types[WorkTypeKind.BOARD].work_type_id),
            _upload(_pdf(1), now, "statement"),
            _upload(_pdf(1), now, "solutions"),
        )


async def test_student_must_reaccept_consent(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A claim under the old notice cannot send until it is accepted again."""
    group = await roster.create(
        TEACHER,
        title="К01",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    student = next(iter(await roster.api.students_of(group.group_id)))
    _ = await roster.claim(group.invite_code, student.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, student.student_id)
    types = {
        item.kind: item for item in await gradebook.scheme(TEACHER, group.group_id)
    }
    created = await _publish(bdz, roster, group, types[WorkTypeKind.TEST].work_type_id)
    now = roster.clock.now()
    with pytest.raises(ConsentRequiredError):
        await bdz.send(STUDENT, created.bdz_id, _upload(_pdf(1), now, "work"))
    _ = await roster.accept(STUDENT)
    assert (
        await bdz.send(STUDENT, created.bdz_id, _upload(_pdf(1), now, "work"))
    ).version == 1


async def test_photo_refused(bdz: BdzBox, roster: Roster, gradebook: Gradebook) -> None:
    """A JPEG is not a PDF."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    with pytest.raises(NotAPdfError):
        await bdz.send(
            STUDENT,
            created.bdz_id,
            _upload(b"\xff\xd8\xff\xe0jpeg", roster.clock.now(), "photo"),
        )


async def test_locked_refused(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A password-protected PDF is refused."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    with pytest.raises(PdfLockedError):
        await bdz.send(
            STUDENT,
            created.bdz_id,
            _upload(_pdf(1, password="secret"), roster.clock.now(), "locked"),
        )


async def test_too_many_pages_refused(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """61 pages is over the cap of 60."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    with pytest.raises(TooManyPagesError):
        await bdz.send(
            STUDENT,
            created.bdz_id,
            _upload(_pdf(61), roster.clock.now(), "long"),
        )


async def test_statement_never_solutions(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """The student receives the statement, not the solutions."""
    group, _, work_type = await _ready(roster, gradebook)
    now = roster.clock.now()
    created = await bdz.create(
        TEACHER,
        group.group_id,
        _draft(now, work_type.work_type_id),
        _upload(_pdf(1), now, "statement-id"),
        _upload(_pdf(1), now, "solutions-id"),
    )
    file_id, title = await bdz.statement(STUDENT, created.bdz_id)
    assert file_id == "tg-statement-id"
    assert title == "Контрольная"


async def test_late_is_marked(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A PDF sent after the deadline is accepted and marked late."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id, hours=-1)
    sent = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "late"),
    )
    assert sent.is_late


async def _verdict_of(session: AsyncSession, work_id: uuid.UUID) -> uuid.UUID:
    row = await session.scalar(
        select(VerdictModel).where(VerdictModel.work_id == work_id),
    )
    assert row is not None
    return row.verdict_id


async def test_resubmission_supersedes_and_voids(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """A new version voids the verdict and leaves the ledger points."""
    group, student, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    now = roster.clock.now()
    first = await bdz.send(STUDENT, created.bdz_id, _upload(_pdf(1), now, "v1"))
    _ = await bdz.submit(_grade(first))
    second = await bdz.send(STUDENT, created.bdz_id, _upload(_pdf(1), now, "v2"))
    assert second.version == 2
    assert not bdz.files.path(first.path).exists()
    verdict = await session.get(
        VerdictModel,
        await _verdict_of(session, first.submission_id),
    )
    assert verdict is not None
    assert verdict.status == VerdictStatus.VOIDED.value
    entry = await session.scalar(
        select(EntryModel).where(EntryModel.item_id == created.item_id),
    )
    assert entry is not None
    assert entry.points == Decimal(7)
    assert entry.student_id == student.student_id


async def test_late_resubmission_voids_a_final_verdict(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """After the deadline a new PDF still voids a teacher's final grade."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id, hours=1)
    first = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "v1"),
    )
    _ = await bdz.submit(_grade(first))
    verdict_id = await _verdict_of(session, first.submission_id)
    _ = await bdz.appeal(
        STUDENT,
        "bdz",
        first.submission_id,
        "Не согласен с баллом за задачу.",
    )
    final = await bdz.finalize(TEACHER, verdict_id, {1: Decimal(5)}, {}, "")
    late = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), created.deadline + timedelta(hours=2), "late"),
    )
    assert late.is_late
    stored = await session.get(VerdictModel, final.verdict_id)
    assert stored is not None
    assert stored.status == VerdictStatus.VOIDED.value
    entry = await session.scalar(
        select(EntryModel).where(EntryModel.item_id == created.item_id),
    )
    assert entry is not None
    assert entry.points == Decimal(5)


async def test_resubmission_refused_while_appeal_open(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """An open appeal blocks a new version."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    sent = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "v1"),
    )
    _ = await bdz.submit(_grade(sent))
    _ = await bdz.appeal(
        STUDENT,
        "bdz",
        sent.submission_id,
        "Не согласен с баллом за задачу.",
    )
    with pytest.raises(AppealOpenError):
        await bdz.send(
            STUDENT,
            created.bdz_id,
            _upload(_pdf(1), roster.clock.now(), "v2"),
        )


async def test_forget_deletes_files_and_reviews(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """Forgetting a student removes the PDF and the verdict."""
    group, student, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    sent = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "v1"),
    )
    _ = await bdz.submit(_grade(sent))
    assert await bdz.forget([student.student_id]) == 1
    assert not bdz.files.path(sent.path).exists()
    left = await session.scalar(
        select(VerdictModel).where(VerdictModel.work_id == sent.submission_id),
    )
    assert left is None


async def test_delete_bdz_removes_reviews(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    session: AsyncSession,
) -> None:
    """Deleting a БДЗ deletes the verdicts about its versions."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    sent = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "v1"),
    )
    _ = await bdz.submit(_grade(sent))
    await bdz.delete(TEACHER, created.bdz_id)
    assert await session.scalar(select(VerdictModel)) is None


async def test_export_zip_holds_the_live_pdf(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """The zip has the student's PDF and a note that it is not graded yet."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    _ = await bdz.send(
        STUDENT,
        created.bdz_id,
        _upload(_pdf(1), roster.clock.now(), "v1"),
    )
    path = await bdz.export(TEACHER, created.bdz_id)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        note = next(name for name in names if name.endswith("разбор.txt"))
        text = archive.read(note).decode()
    assert any(name.endswith("работа.pdf") for name in names)
    assert "Проверки пока нет." in text


def _pdfs_on_disk(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "files").rglob("*.pdf"))


async def test_failed_create_leaves_no_file(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    tmp_path: Path,
) -> None:
    """A locked solutions PDF takes the already stored statement with it."""
    group, _, work_type = await _ready(roster, gradebook)
    now = roster.clock.now()
    with pytest.raises(PdfLockedError):
        _ = await bdz.create(
            TEACHER,
            group.group_id,
            _draft(now, work_type.work_type_id),
            _upload(_pdf(1), now, "statement"),
            _upload(_pdf(1, password="secret"), now, "solutions"),
        )
    assert _pdfs_on_disk(tmp_path) == []


async def test_failed_send_leaves_no_file(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any failure after the PDF is stored deletes it, not only refusals."""
    group, _, work_type = await _ready(roster, gradebook)
    created = await _publish(bdz, roster, group, work_type.work_type_id)
    before = _pdfs_on_disk(tmp_path)

    async def broken(*_: object) -> None:
        msg = "database went away"
        raise RuntimeError(msg)

    monkeypatch.setattr(bdz.send._submissions, "add", broken)
    with pytest.raises(RuntimeError, match="went away"):
        _ = await bdz.send(
            STUDENT,
            created.bdz_id,
            _upload(_pdf(2), roster.clock.now(), "work"),
        )
    assert _pdfs_on_disk(tmp_path) == before


async def test_create_without_solutions(
    bdz: BdzBox,
    roster: Roster,
    gradebook: Gradebook,
) -> None:
    """A БДЗ may come without a solutions PDF; the agent then solves it itself."""
    group, _, work_type = await _ready(roster, gradebook)
    now = roster.clock.now()
    created = await bdz.create(
        TEACHER,
        group.group_id,
        _draft(now, work_type.work_type_id),
        _upload(_pdf(2), now, "statement"),
        None,
    )
    assert created.solutions_path is None
    sheet = await bdz.source.sheet(created.bdz_id)
    assert sheet.solutions_path is None
    assert sheet.solutions_pages is None
    assert sheet.statement_pages == 2
