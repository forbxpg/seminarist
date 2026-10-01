"""Homework's use cases over one session, for integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.core.files import FileStore
from smr.homework.application.use_cases import (
    AddFile,
    AssignmentRoster,
    ClearDraft,
    CopyAssignment,
    CreateAssignment,
    DeleteAssignment,
    DeleteStudentFiles,
    ExportSubmissions,
    GradeSubmission,
    ListAssignments,
    MyWork,
    OpenSubmission,
    QueueReminders,
    ReviewQueue,
    StudentAssignments,
    Submit,
    UpdateAssignment,
)
from smr.homework.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemyFiles,
    SqlAlchemySubmissions,
)

if TYPE_CHECKING:
    from pathlib import Path

    from gradebook_kit import Gradebook
    from notifications_kit import Notifications
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("MAX_FILES", "Homework", "homework")

MAX_FILES = 3


@final
class Homework:
    """Homework's use cases bound to one session and a temporary data directory."""

    def __init__(
        self,
        session: AsyncSession,
        gradebook: Gradebook,
        notifications: Notifications,
        data_dir: Path,
    ) -> None:
        assignments = SqlAlchemyAssignments(session)
        submissions = SqlAlchemySubmissions(session)
        stored = SqlAlchemyFiles(session)
        uow = SqlAlchemyUnitOfWork(session)
        audit = SqlAlchemyAuditLog(session)
        guard = AdminGuard({1})
        roster = gradebook.roster
        ledger = gradebook.ledger
        notifier = notifications.notifier
        clock = roster.clock
        files = FileStore(data_dir, max_bytes=1024)
        self.data_dir: Path = data_dir
        self.files: FileStore = files
        self.gradebook: Gradebook = gradebook
        self.notifications: Notifications = notifications
        self.create: CreateAssignment = CreateAssignment(
            assignments,
            roster.api,
            ledger,
            notifier,
            files,
            uow,
            audit,
            guard,
            clock,
        )
        self.update: UpdateAssignment = UpdateAssignment(
            assignments,
            roster.api,
            ledger,
            uow,
            audit,
            guard,
        )
        self.copy: CopyAssignment = CopyAssignment(
            assignments,
            files,
            self.create,
            guard,
        )
        self.delete: DeleteAssignment = DeleteAssignment(
            assignments,
            stored,
            ledger,
            files,
            uow,
            audit,
            guard,
        )
        self.list: ListAssignments = ListAssignments(assignments, submissions, guard)
        self.roster_view: AssignmentRoster = AssignmentRoster(
            assignments,
            submissions,
            roster.api,
            guard,
        )
        self.mine: StudentAssignments = StudentAssignments(
            assignments,
            submissions,
            stored,
            roster.api,
            ledger,
        )
        self.add_file: AddFile = AddFile(
            assignments,
            submissions,
            stored,
            roster.api,
            files,
            uow,
            MAX_FILES,
        )
        self.clear: ClearDraft = ClearDraft(
            assignments,
            submissions,
            stored,
            roster.api,
            files,
            uow,
        )
        self.submit: Submit = Submit(
            assignments,
            submissions,
            stored,
            roster.api,
            files,
            uow,
            audit,
            clock,
        )
        self.work: MyWork = MyWork(assignments, submissions, stored, roster.api, ledger)
        self.queue: ReviewQueue = ReviewQueue(submissions, guard)
        self.open: OpenSubmission = OpenSubmission(
            assignments,
            submissions,
            stored,
            roster.api,
            guard,
        )
        self.grade: GradeSubmission = GradeSubmission(
            assignments,
            submissions,
            roster.api,
            ledger,
            notifier,
            uow,
            guard,
        )
        self.reminders: QueueReminders = QueueReminders(
            assignments,
            submissions,
            roster.api,
            notifier,
            uow,
            clock,
        )
        self.forget_files: DeleteStudentFiles = DeleteStudentFiles(stored, files, uow)
        self.export: ExportSubmissions = ExportSubmissions(
            assignments,
            submissions,
            stored,
            roster.api,
            files,
            guard,
            clock,
            data_dir,
        )


@pytest.fixture
def homework(
    session: AsyncSession,
    gradebook: Gradebook,
    notifications: Notifications,
    tmp_path: Path,
) -> Homework:
    """Give homework's use cases over the test's session and a temporary disk."""
    return Homework(session, gradebook, notifications, tmp_path)
