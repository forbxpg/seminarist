"""БДЗ use cases over one session, with the real review source."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from smr.bdz.application.services import BdzReviewSource
from smr.bdz.application.use_cases import (
    BdzLimits,
    BdzStatement,
    CreateBdz,
    DeleteBdz,
    DeleteStudentBdzFiles,
    ExportBdz,
    MoveBdz,
    SendBdz,
)
from smr.bdz.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemySubmissions,
)
from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.core.files import FileStore
from smr.review.application.services import Reviews
from smr.review.application.use_cases import (
    FileAppeal,
    FinalizeByTeacher,
    PendingWorks,
    SubmitVerdict,
)
from smr.review.infrastructure.repositories import SqlAlchemyAppeals, SqlAlchemyVerdicts

if TYPE_CHECKING:
    from pathlib import Path

    from gradebook_kit import Gradebook
    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("BdzBox", "bdz")


@final
class BdzBox:
    """The use cases a БДЗ test drives."""

    def __init__(
        self,
        session: AsyncSession,
        roster: Roster,
        gradebook: Gradebook,
        notifications: Notifications,
        directory: Path,
    ) -> None:
        assignments = SqlAlchemyAssignments(session)
        submissions = SqlAlchemySubmissions(session)
        audit = SqlAlchemyAuditLog(session)
        uow = SqlAlchemyUnitOfWork(session)
        guard = AdminGuard({1})
        files = FileStore(directory, 20 * 1024 * 1024)
        limits = BdzLimits(60)
        verdicts = SqlAlchemyVerdicts(session)
        appeals = SqlAlchemyAppeals(session)
        reviews = Reviews(verdicts, appeals)
        source = BdzReviewSource(assignments, submissions, roster.api, gradebook.ledger)
        sources = (source,)
        self.files: FileStore = files
        self.source: BdzReviewSource = source
        self.create: CreateBdz = CreateBdz(
            assignments,
            roster.api,
            gradebook.ledger,
            notifications.notifier,
            files,
            audit,
            uow,
            roster.clock,
            guard,
            limits,
        )
        self.send: SendBdz = SendBdz(
            assignments,
            submissions,
            roster.api,
            reviews,
            files,
            audit,
            uow,
            roster.clock,
            limits,
        )
        self.statement: BdzStatement = BdzStatement(assignments, roster.api)
        self.move: MoveBdz = MoveBdz(
            assignments,
            roster.api,
            gradebook.ledger,
            audit,
            uow,
            guard,
        )
        self.delete: DeleteBdz = DeleteBdz(
            assignments,
            submissions,
            roster.api,
            gradebook.ledger,
            reviews,
            files,
            audit,
            uow,
            guard,
        )
        self.export: ExportBdz = ExportBdz(
            assignments,
            submissions,
            roster.api,
            reviews,
            files,
            guard,
            roster.clock,
            directory,
        )
        self.forget: DeleteStudentBdzFiles = DeleteStudentBdzFiles(
            assignments,
            submissions,
            reviews,
            files,
            uow,
        )
        self.pending: PendingWorks = PendingWorks(sources, verdicts)
        self.submit: SubmitVerdict = SubmitVerdict(
            sources,
            verdicts,
            notifications.notifier,
            audit,
            uow,
            roster.clock,
        )
        self.appeal: FileAppeal = FileAppeal(
            sources,
            verdicts,
            appeals,
            notifications.notifier,
            audit,
            uow,
            roster.clock,
        )
        self.finalize: FinalizeByTeacher = FinalizeByTeacher(
            sources,
            verdicts,
            appeals,
            notifications.notifier,
            audit,
            uow,
            roster.clock,
            guard,
        )


@pytest.fixture
def bdz(
    session: AsyncSession,
    roster: Roster,
    gradebook: Gradebook,
    notifications: Notifications,
    tmp_path: Path,
) -> BdzBox:
    """Give the БДЗ use cases over the test's session."""
    return BdzBox(session, roster, gradebook, notifications, tmp_path)
