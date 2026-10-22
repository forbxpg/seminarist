"""Dialogs through aiogram-dialog's test client and fake use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING, cast, override

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, SendDocument, SendMessage
from aiogram.types import Chat, Document, Message, PhotoSize, Update
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.test_tools import BotClient, MockMessageManager
from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from smr.bdz.application.use_cases import SendBdz, StudentBdz, StudentBdzList, Upload
from smr.bdz.domain import Bdz, BdzSubmission, SubmissionStatus
from smr.bot._app import build_dispatcher
from smr.bot.dialogs.admin import admin_dialogs
from smr.bot.dialogs.student.consent import consent_dialog
from smr.bot.dialogs.student.join import join_dialog
from smr.bot.dialogs.student.menu import student_dialog
from smr.bot.handlers.bindings import router as bindings_router
from smr.bot.handlers.errors import router as errors_router
from smr.bot.handlers.start import router as start_router
from smr.bot.states import AdminSG, ReviewSG, StudentSG
from smr.core.access import AdminGuard
from smr.core.files import FileStore
from smr.review.application.ports import TaskSheet
from smr.review.application.use_cases import (
    FileAppeal,
    FinalizeByTeacher,
    MyVerdict,
    OpenForTeacher,
    QueueItem,
    TeacherQueue,
    TeacherView,
    VerdictView,
)
from smr.review.domain import (
    Appeal,
    AppealStatus,
    GraderKind,
    SchemeTask,
    TaskVerdict,
    Verdict,
    VerdictStatus,
)
from smr.roster.application.contracts import RosterApi
from smr.roster.application.use_cases import (
    AcceptConsent,
    ClaimableNames,
    ClaimStudent,
    Membership,
    Memberships,
    ResolveInvite,
    SetJournalNumber,
)
from smr.roster.domain import (
    CONSENT_VERSION,
    BindingStatus,
    Group,
    GroupSettings,
    GroupStatus,
    Student,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO

    from aiogram.fsm.state import State
    from aiogram.methods.base import TelegramMethod
    from aiogram.types import Downloadable

_NOW = datetime(2026, 10, 8, 7, tzinfo=UTC)
_TEACHER = 1
_STUDENT = 42
_BROKEN = "Что-то пошло не так"


@dataclass
class _World:
    """What the fakes remember between the clicks of one test."""

    mode: str
    group: Group
    student: Student
    accepted: bool = False
    claimed: list[uuid.UUID] = field(default_factory=list)
    uploads: list[bytes] = field(default_factory=list)
    appeals: list[str] = field(default_factory=list)
    scores: dict[int, Decimal] = field(default_factory=dict)
    comment: str | None = None
    graded: bool = False
    journal: int | None = None


def _group() -> Group:
    return Group(
        group_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        title="К01-261",
        subject="Дискретная математика",
        semester="осень 2026",
        invite_code="seminar",
        status=GroupStatus.ACTIVE,
        archived_at=None,
        settings=GroupSettings(),
    )


def _student(
    group: Group,
    *,
    name: str,
    binding: BindingStatus,
    consent: str | None,
) -> Student:
    return Student(
        student_id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
        group_id=group.group_id,
        full_name=name,
        tg_user_id=None,
        binding=binding,
        binding_requested_at=None,
        consent_version=consent,
        consent_at=None,
    )


def _world(mode: str, name: str, binding: BindingStatus, consent: str | None) -> _World:
    group = _group()
    return _World(
        mode=mode,
        group=group,
        student=_student(group, name=name, binding=binding, consent=consent),
    )


@dataclass
class _Bound:
    """A fake use case that reads and writes one test world."""

    _world: _World


class _Resolve(_Bound):
    async def __call__(self, _invite_code: str) -> Group:
        return self._world.group


class _Names(_Bound):
    async def __call__(self, _invite_code: str) -> list[Student]:
        return [self._world.student]


class _Claim(_Bound):
    async def __call__(
        self,
        _invite_code: str,
        student_id: uuid.UUID,
        tg_user_id: int,
        _consent_version: str,
    ) -> Membership:
        self._world.claimed.append(student_id)
        pending = replace(
            self._world.student,
            binding=BindingStatus.PENDING,
            tg_user_id=tg_user_id,
        )
        return Membership(self._world.group, pending)


class _Roster(_Bound):
    async def student(self, student_id: uuid.UUID) -> Student | None:
        if student_id != self._world.student.student_id:
            return None
        return self._world.student


class _Memberships(_Bound):
    async def __call__(self, _user_id: int) -> list[Membership]:
        if self._world.mode == "empty":
            return []
        return [Membership(self._world.group, self._world.student)]


class _Accept(_Bound):
    async def __call__(self, _tg_user_id: int) -> None:
        self._world.accepted = True
        self._world.mode = "bound"
        self._world.student = replace(
            self._world.student,
            binding=BindingStatus.BOUND,
            consent_version=CONSENT_VERSION,
        )


class _Journal(_Bound):
    async def __call__(
        self,
        _actor: int,
        _student_id: uuid.UUID,
        number: int | None,
    ) -> None:
        self._world.journal = number
        self._world.student = replace(self._world.student, journal_no=number)


class _BdzList(_Bound):
    async def __call__(
        self,
        _tg_user_id: int,
        _group_id: uuid.UUID,
    ) -> list[StudentBdz]:
        return [_student_bdz(self._world)]


class _Send(_Bound):
    async def __call__(
        self,
        _actor: int,
        _bdz_id: uuid.UUID,
        upload: Upload,
    ) -> BdzSubmission:
        self._world.uploads.append(upload.data)
        return _submission(self._world)


class _Mine(_Bound):
    async def __call__(
        self,
        _actor: int,
        _source: str,
        _work_id: uuid.UUID,
    ) -> VerdictView:
        return VerdictView(
            _verdict(VerdictStatus.PUBLISHED),
            can_appeal=True,
            appeal_until=_NOW,
            appeal=None,
        )


class _Appeal(_Bound):
    async def __call__(
        self,
        _actor: int,
        _source: str,
        _work_id: uuid.UUID,
        text: str,
    ) -> Appeal:
        self._world.appeals.append(text)
        return Appeal(
            appeal_id=uuid.UUID("00000000-0000-4000-8000-000000000010"),
            verdict_id=_verdict(VerdictStatus.PUBLISHED).verdict_id,
            text=text,
            status=AppealStatus.OPEN,
            filed_at=_NOW,
            resolved_at=None,
            resolution_verdict_id=None,
        )


class _Queue(_Bound):
    async def __call__(self, _actor: int) -> list[QueueItem]:
        if self._world.graded:
            return []
        verdict = _verdict(VerdictStatus.MANUAL)
        return [QueueItem(verdict, None, "Контрольная", 2, is_late=False)]


class _Open(_Bound):
    async def __call__(self, _actor: int, _verdict_id: uuid.UUID) -> TeacherView:
        verdict = _verdict(VerdictStatus.MANUAL)
        return TeacherView(verdict, None, "files/hw.pdf", _sheet())


class _Finalize(_Bound):
    async def __call__(
        self,
        _actor: int,
        _verdict_id: uuid.UUID,
        scores: dict[int, Decimal],
        _explanations: dict[int, str],
        summary: str,
    ) -> Verdict:
        self._world.scores = dict(scores)
        self._world.comment = summary
        self._world.graded = True
        return _verdict(VerdictStatus.FINAL)


class _Fakes(Provider):
    def __init__(self, world: _World, files: FileStore) -> None:
        super().__init__(scope=Scope.APP)
        self._world: _World = world
        self._files: FileStore = files

    @provide(scope=Scope.APP)
    def resolve(self) -> ResolveInvite:
        return _as(_Resolve(self._world), ResolveInvite)

    @provide(scope=Scope.APP)
    def names(self) -> ClaimableNames:
        return _as(_Names(self._world), ClaimableNames)

    @provide(scope=Scope.APP)
    def claim(self) -> ClaimStudent:
        return _as(_Claim(self._world), ClaimStudent)

    @provide(scope=Scope.APP)
    def roster(self) -> RosterApi:
        return _as(_Roster(self._world), RosterApi)

    @provide(scope=Scope.APP)
    def memberships(self) -> Memberships:
        return _as(_Memberships(self._world), Memberships)

    @provide(scope=Scope.APP)
    def accept(self) -> AcceptConsent:
        return _as(_Accept(self._world), AcceptConsent)

    @provide(scope=Scope.APP)
    def journal(self) -> SetJournalNumber:
        return _as(_Journal(self._world), SetJournalNumber)

    @provide(scope=Scope.APP)
    def bdz_list(self) -> StudentBdzList:
        return _as(_BdzList(self._world), StudentBdzList)

    @provide(scope=Scope.APP)
    def send_bdz(self) -> SendBdz:
        return _as(_Send(self._world), SendBdz)

    @provide(scope=Scope.APP)
    def mine(self) -> MyVerdict:
        return _as(_Mine(self._world), MyVerdict)

    @provide(scope=Scope.APP)
    def appeal(self) -> FileAppeal:
        return _as(_Appeal(self._world), FileAppeal)

    @provide(scope=Scope.APP)
    def queue(self) -> TeacherQueue:
        return _as(_Queue(self._world), TeacherQueue)

    @provide(scope=Scope.APP)
    def opened(self) -> OpenForTeacher:
        return _as(_Open(self._world), OpenForTeacher)

    @provide(scope=Scope.APP)
    def finalize(self) -> FinalizeByTeacher:
        return _as(_Finalize(self._world), FinalizeByTeacher)

    @provide(scope=Scope.APP)
    def guard(self) -> AdminGuard:
        return AdminGuard([_TEACHER])

    @provide(scope=Scope.APP)
    def files(self) -> FileStore:
        return self._files


def _as[T](value: object, kind: type[T]) -> T:
    """Hand dishka a fake where the dialog asks for the real use case."""
    del kind
    return cast("T", value)


class RecordingBot(Bot):
    """Records texts the dialogs send, and serves a tiny PDF download."""

    def __init__(self) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Skip Telegram's session; this bot only records calls."""
        self.texts: list[str] = []

    @property
    @override
    def id(self) -> int:
        """Telegram's id of this stub."""
        return 1

    @override
    def __hash__(self) -> int:
        """Hash like aiogram's fake bot: one stable value."""
        return 1

    @override
    def __eq__(self, other: object) -> bool:
        """Equal only to itself, matching aiogram's fake bot."""
        return self is other

    @override
    async def download(
        self,
        file: str | Downloadable,
        destination: BinaryIO | Path | str | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        seek: bool = True,
    ) -> BinaryIO | None:
        """Return a one-page PDF instead of calling Telegram."""
        del file, destination, timeout, chunk_size, seek
        return BytesIO(b"%PDF-1.4")

    @override
    async def __call__[T](
        self,
        method: TelegramMethod[T],
        request_timeout: int | None = None,
    ) -> T:
        """Record a sent text or document caption."""
        del request_timeout
        if isinstance(method, AnswerCallbackQuery):
            if method.text:
                self.texts.append(method.text)
            answered: object = True
            return cast("T", answered)
        if isinstance(method, SendMessage):
            self.texts.append(method.text)
            return cast("T", _stub(method.text))
        if isinstance(method, SendDocument):
            self.texts.append(method.caption or "")
            return cast("T", _stub(method.caption or ""))
        msg = type(method).__name__
        raise RuntimeError(msg)


def _stub(text: str) -> Message:
    return Message(
        message_id=1,
        date=_NOW,
        chat=Chat(id=1, type="private"),
        text=text,
    )


@dataclass
class _Stage:
    """One dispatcher, two people, and the fakes behind the dialogs."""

    world: _World
    bot: RecordingBot
    manager: MockMessageManager
    container: AsyncContainer
    student: BotClient
    teacher: BotClient
    opened: tuple[State, dict[str, str]] = field(
        default_factory=lambda: (StudentSG.menu, {}),
    )

    async def open(self, client: BotClient, state: State, data: dict[str, str]) -> None:
        self.opened = (state, data)
        await client.send("/open")

    async def close(self) -> None:
        await self.container.close()
        _free_shared_routers()


def _launcher(stage: _Stage) -> Router:
    router = Router()

    @router.message(Command("open"))
    async def _open(
        _message: Message,
        dialog_manager: DialogManager,
    ) -> None:
        """Start the dialog the test prepared."""
        state, data = stage.opened
        await dialog_manager.start(state, data=data, mode=StartMode.RESET_STACK)

    return router


def _free_shared_routers() -> None:
    """Module routers can sit on one dispatcher; drop that link before the next one."""
    shared = (
        errors_router,
        start_router,
        bindings_router,
        join_dialog,
        student_dialog,
        consent_dialog,
        *admin_dialogs(),
    )
    for router in shared:
        router._parent_router = None


async def _stage(tmp_path: Path, world: _World) -> _Stage:
    _free_shared_routers()
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    _ = (files_dir / "hw.pdf").write_bytes(b"%PDF-1.4")
    store = FileStore(tmp_path, max_bytes=20 * 1024 * 1024)
    container = make_async_container(_Fakes(world, store))
    bot = RecordingBot()
    manager = MockMessageManager()
    dispatcher = build_dispatcher(
        container,
        MemoryStorage(),
        AdminGuard([_TEACHER]),
        manager,
    )
    stage = _Stage(
        world=world,
        bot=bot,
        manager=manager,
        container=container,
        student=BotClient(dispatcher, user_id=_STUDENT, bot=bot),
        teacher=BotClient(dispatcher, user_id=_TEACHER, bot=bot),
    )
    dispatcher.include_router(_launcher(stage))
    await dispatcher.emit_startup()
    return stage


def _windows(manager: MockMessageManager) -> str:
    parts = [message.text or message.caption or "" for message in manager.sent_messages]
    return "\n".join(parts)


def _ok(bot: RecordingBot) -> None:
    assert all(_BROKEN not in text for text in bot.texts)


def _bdz() -> Bdz:
    return Bdz(
        bdz_id=uuid.UUID("00000000-0000-4000-8000-000000000003"),
        group_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
        work_type_id=uuid.UUID("00000000-0000-4000-8000-000000000004"),
        item_id=None,
        title="Контрольная",
        deadline=_NOW,
        max_points=Decimal(10),
        statement_path="files/hw.pdf",
        statement_tg_file_id="stmt",
        statement_pages=1,
        solutions_path=None,
        solutions_tg_file_id=None,
        solutions_pages=None,
        created_at=_NOW,
    )


def _submission(world: _World) -> BdzSubmission:
    return BdzSubmission(
        submission_id=uuid.UUID("00000000-0000-4000-8000-000000000005"),
        bdz_id=_bdz().bdz_id,
        student_id=world.student.student_id,
        version=1,
        status=SubmissionStatus.LIVE,
        path="files/hw.pdf",
        tg_file_id="doc",
        tg_file_unique_id="doc-u",
        size=8,
        sha256="abc",
        pages=1,
        sent_at=_NOW,
        is_late=False,
    )


def _student_bdz(world: _World) -> StudentBdz:
    return StudentBdz(
        bdz=_bdz(),
        submission=_submission(world),
        status=VerdictStatus.PUBLISHED,
        total=Decimal(5),
        published_at=_NOW,
        can_appeal=True,
        tasks=(SchemeTask(1, Decimal(10)),),
    )


def _verdict(status: VerdictStatus) -> Verdict:
    return Verdict(
        verdict_id=uuid.UUID("00000000-0000-4000-8000-000000000006"),
        source="bdz",
        work_id=uuid.UUID("00000000-0000-4000-8000-000000000005"),
        work_sha256="abc",
        task_ref=_bdz().bdz_id,
        student_ref=uuid.UUID("00000000-0000-4000-8000-000000000002"),
        grader_kind=GraderKind.AGENT,
        grader="fake",
        status=status,
        total=Decimal(5),
        max_points=Decimal(10),
        summary="Кратко.",
        pages_seen=1,
        created_at=_NOW,
        published_at=_NOW,
        tasks=(
            TaskVerdict(
                1,
                Decimal(5),
                Decimal(10),
                "Верно.",
                unreadable=False,
                unsure=False,
                manipulation=False,
                pages=(1,),
            ),
        ),
    )


def _sheet() -> TaskSheet:
    return TaskSheet(
        task_ref=_bdz().bdz_id,
        title="Контрольная",
        scheme=(SchemeTask(1, Decimal(10)),),
        max_points=Decimal(10),
        statement_path="files/hw.pdf",
        statement_pages=1,
        solutions_path=None,
        solutions_pages=None,
    )


def _ids(world: _World) -> dict[str, str]:
    return {
        "group_id": str(world.group.group_id),
        "bdz_id": str(_bdz().bdz_id),
        "student_id": str(world.student.student_id),
    }


async def _click(client: BotClient, manager: MockMessageManager, pattern: str) -> None:
    await client.click(manager.last_message(), InlineButtonTextLocator(pattern))


async def _file(client: BotClient, *, photo: bool) -> None:
    if photo:
        message = Message(
            message_id=client._new_message_id(),
            date=_NOW,
            chat=client.chat,
            from_user=client.user,
            photo=[
                PhotoSize(
                    file_id="photo-1",
                    file_unique_id="photo-u",
                    width=80,
                    height=80,
                    file_size=8,
                ),
            ],
        )
    else:
        message = Message(
            message_id=client._new_message_id(),
            date=_NOW,
            chat=client.chat,
            from_user=client.user,
            document=Document(
                file_id="doc-1",
                file_unique_id="doc-u",
                file_name="work.pdf",
                mime_type="application/pdf",
                file_size=8,
            ),
        )
    await client.dp.feed_update(
        client.bot,
        Update(update_id=client._new_update_id(), message=message),
    )


async def test_joining_a_group_asks_for_consent_and_a_name(tmp_path: Path) -> None:
    """A link shows the notice, the free name, and the waiting screen."""
    world = _world("empty", "Иванов Иван", BindingStatus.UNBOUND, None)
    stage = await _stage(tmp_path, world)
    try:
        await stage.student.send("/start seminar")
        text = _windows(stage.manager)
        assert "К01-261" in text
        assert "Обработка персональных данных" in text
        await _click(stage.student, stage.manager, r"✅ Согласен")
        await _click(stage.student, stage.manager, r"Иванов Иван")
        assert "Иванов Иван" in _windows(stage.manager)
        await _click(stage.student, stage.manager, r"Да, это я")
        assert "Заявка отправлена" in _windows(stage.manager)
        assert world.claimed == [world.student.student_id]
        assert any("Иванов Иван" in text for text in stage.bot.texts)
        _ok(stage.bot)
    finally:
        await stage.close()


async def test_an_old_consent_is_shown_again_before_the_menu(tmp_path: Path) -> None:
    """A bound student with an old notice accepts it and lands in the menu."""
    world = _world("stale", "Петров Пётр", BindingStatus.BOUND, "2020-01-01")
    stage = await _stage(tmp_path, world)
    try:
        await stage.student.send("/start")
        assert "Обработка персональных данных" in _windows(stage.manager)
        await _click(stage.student, stage.manager, r"Принимаю")
        assert world.accepted
        menu = _windows(stage.manager)
        assert "Петров Пётр" in menu
        assert "К01-261" in menu
        _ok(stage.bot)
    finally:
        await stage.close()


async def test_a_pdf_is_accepted_and_a_photo_is_refused(tmp_path: Path) -> None:
    """БДЗ takes one PDF and answers a photo with the scan hint."""
    world = _world("bound", "Иванов Иван", BindingStatus.BOUND, CONSENT_VERSION)
    stage = await _stage(tmp_path, world)
    try:
        await stage.open(stage.student, StudentSG.bdz_upload, _ids(world))
        await _file(stage.student, photo=True)
        assert any(
            text.startswith("Пришлите БДЗ одним PDF-файлом") for text in stage.bot.texts
        )
        assert world.uploads == []
        await _file(stage.student, photo=False)
        assert world.uploads == [b"%PDF-1.4"]
        assert any(text.startswith("Принято, версия 1") for text in stage.bot.texts)
        assert "Контрольная" in _windows(stage.manager)
        _ok(stage.bot)
    finally:
        await stage.close()


async def test_a_student_reads_the_breakdown_and_files_an_appeal(
    tmp_path: Path,
) -> None:
    """The breakdown is sent, then one appeal goes to the teacher."""
    world = _world("bound", "Иванов Иван", BindingStatus.BOUND, CONSENT_VERSION)
    stage = await _stage(tmp_path, world)
    try:
        await stage.open(stage.student, StudentSG.bdz, _ids(world))
        await _click(stage.student, stage.manager, r"🧾 Разбор")
        assert any("5 из 10" in text for text in stage.bot.texts)
        assert "Апелляцию можно подать" in _windows(stage.manager)
        await _click(stage.student, stage.manager, r"⚖️ Апелляция")
        await stage.student.send("Не согласен с баллом за первую задачу.")
        await _click(stage.student, stage.manager, r"Отправить")
        assert world.appeals == ["Не согласен с баллом за первую задачу."]
        assert any("Апелляция отправлена" in text for text in stage.bot.texts)
        _ok(stage.bot)
    finally:
        await stage.close()


async def test_the_teacher_grades_a_manual_review(tmp_path: Path) -> None:
    """The queue opens a work and a typed score becomes the final grade."""
    world = _world("empty", "Иванов Иван", BindingStatus.UNBOUND, None)
    stage = await _stage(tmp_path, world)
    try:
        await stage.open(stage.teacher, ReviewSG.queue, {})
        await _click(stage.teacher, stage.manager, r"Контрольная v2 — ручная")
        assert "разбор агента" in _windows(stage.manager)
        await _click(stage.teacher, stage.manager, r"Оценить")
        await stage.teacher.send("1:5")
        await stage.teacher.send(".")
        await _click(stage.teacher, stage.manager, r"Отправить")
        assert world.scores == {1: Decimal(5)}
        assert world.comment is not None
        assert not world.comment
        assert any("Оценка отправлена студенту." in text for text in stage.bot.texts)
        assert "Очередь пуста." in _windows(stage.manager)
        _ok(stage.bot)
    finally:
        await stage.close()


async def test_the_teacher_sets_a_journal_number(tmp_path: Path) -> None:
    """A typed journal number is stored and shown on the student card."""
    world = _world("empty", "Иванов Иван", BindingStatus.UNBOUND, None)
    stage = await _stage(tmp_path, world)
    try:
        await stage.open(
            stage.teacher,
            AdminSG.journal_no,
            {"student_id": str(world.student.student_id)},
        )
        await stage.teacher.send("7")
        assert world.journal == 7
        assert "Номер в журнале: 7" in _windows(stage.manager)
        _ok(stage.bot)
    finally:
        await stage.close()
