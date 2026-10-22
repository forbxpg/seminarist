"""The review's use cases over one session, with an in-memory source of work."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from operator import attrgetter
from typing import TYPE_CHECKING, final

import pytest

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.review.application.ports import ReviewSource, TaskSheet, WorkPage, WorkRef
from smr.review.application.services import Reviews
from smr.review.application.use_cases import (
    FileAppeal,
    FinalizeByTeacher,
    MyVerdict,
    OpenForTeacher,
    PendingWorks,
    SubmitVerdict,
    TaskSheetFor,
    TeacherQueue,
    WorkFile,
)
from smr.review.domain import SchemeTask
from smr.review.infrastructure.repositories import SqlAlchemyAppeals, SqlAlchemyVerdicts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.core.clock import Clock

__all__ = ("FakeSource", "Review", "review")


@final
class FakeSource:
    """`ReviewSource` kept in memory. `name` is `bdz`."""

    name: str = "bdz"

    def __init__(self) -> None:
        self.works: dict[uuid.UUID, WorkRef] = {}
        self.sheets: dict[uuid.UUID, TaskSheet] = {}
        self.owners: dict[uuid.UUID, int] = {}
        self.paths: dict[uuid.UUID, str] = {}
        self.grades: list[tuple[uuid.UUID, Decimal, int | None, str | None]] = []

    def add(
        self,
        student_id: uuid.UUID,
        owner: int,
        *,
        pages: int = 1,
        maximum: str = "10",
    ) -> WorkRef:
        """Put one live version into the source.

        Args:
            student_id: uuid.UUID - The roster row.
            owner: int - The account that owns it.
            pages: int - How many pages the file has.
            maximum: str - The single task's maximum.

        Returns:
            WorkRef - The version.

        """
        work_id = uuid.uuid4()
        task_ref = uuid.uuid4()
        cap = Decimal(maximum)
        work = WorkRef(
            work_id=work_id,
            task_ref=task_ref,
            student_ref=student_id,
            version=1,
            sha256="ab" * 32,
            pages=pages,
            sent_at=datetime(2026, 10, 2, 9, tzinfo=UTC),
            is_late=False,
            title="БДЗ",
        )
        self.works[work_id] = work
        self.owners[work_id] = owner
        self.paths[work_id] = f"files/2026-10/{work_id.hex}.pdf"
        self.sheets[task_ref] = TaskSheet(
            task_ref=task_ref,
            title="БДЗ",
            scheme=(SchemeTask(1, cap),),
            max_points=cap,
            statement_path="files/2026-10/statement.pdf",
            statement_pages=1,
            solutions_path="files/2026-10/solutions.pdf",
            solutions_pages=1,
        )
        return work

    async def live_works(self) -> list[WorkRef]:
        """List the versions, oldest first."""
        return sorted(self.works.values(), key=attrgetter("sent_at"))

    async def work(
        self,
        work_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> WorkRef | None:
        """Read one version. The lock is a no-op in memory."""
        _ = lock
        return self.works.get(work_id)

    async def sheet(self, task_ref: uuid.UUID) -> TaskSheet:
        """Read the scheme."""
        return self.sheets[task_ref]

    async def work_path(self, work_id: uuid.UUID) -> str:
        """Tell where the PDF is."""
        return self.paths[work_id]

    async def pages(self, work_id: uuid.UUID) -> tuple[WorkPage, ...]:
        """The one PDF, when the version is known."""
        work = self.works.get(work_id)
        if work is None:
            return ()
        return (WorkPage(self.paths[work_id], "pdf", work.pages),)

    async def belongs_to(self, work_id: uuid.UUID, tg_user_id: int) -> bool:
        """Tell whether the account owns the version."""
        return self.owners.get(work_id) == tg_user_id

    async def apply_grade(
        self,
        work_id: uuid.UUID,
        total: Decimal,
        *,
        teacher: int | None,
        agent: str | None,
    ) -> None:
        """Remember the grade instead of writing the ledger."""
        self.grades.append((work_id, total, teacher, agent))


@final
class Review:
    """The review's use cases bound to one session and one fake source."""

    def __init__(
        self,
        session: AsyncSession,
        clock: Clock,
        notifications: Notifications,
    ) -> None:
        verdicts = SqlAlchemyVerdicts(session)
        appeals = SqlAlchemyAppeals(session)
        audit = SqlAlchemyAuditLog(session)
        uow = SqlAlchemyUnitOfWork(session)
        guard = AdminGuard({1})
        self.source: FakeSource = FakeSource()
        sources: Sequence[ReviewSource] = (self.source,)
        self.api: Reviews = Reviews(verdicts, appeals)
        self.pending: PendingWorks = PendingWorks(sources, verdicts)
        self.sheet: TaskSheetFor = TaskSheetFor(sources)
        self.file: WorkFile = WorkFile(sources)
        self.submit: SubmitVerdict = SubmitVerdict(
            sources,
            verdicts,
            notifications.notifier,
            audit,
            uow,
            clock,
        )
        self.mine: MyVerdict = MyVerdict(sources, verdicts, appeals, clock)
        self.appeal: FileAppeal = FileAppeal(
            sources,
            verdicts,
            appeals,
            notifications.notifier,
            audit,
            uow,
            clock,
        )
        self.queue: TeacherQueue = TeacherQueue(sources, verdicts, appeals, guard)
        self.open: OpenForTeacher = OpenForTeacher(sources, verdicts, appeals, guard)
        self.finalize: FinalizeByTeacher = FinalizeByTeacher(
            sources,
            verdicts,
            appeals,
            notifications.notifier,
            audit,
            uow,
            clock,
            guard,
        )


@pytest.fixture
def review(
    session: AsyncSession,
    roster: Roster,
    notifications: Notifications,
) -> Review:
    """Give the review's use cases over the test's session."""
    return Review(session, roster.clock, notifications)
