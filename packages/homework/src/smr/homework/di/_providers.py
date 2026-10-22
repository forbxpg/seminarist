"""Homework's repositories and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.core.access import AdminGuard
from smr.core.clock import Clock
from smr.core.config import StorageSettings
from smr.core.database import UnitOfWork
from smr.core.files import FileStore
from smr.homework.application.ports import (
    AssignmentRepository,
    FileRepository,
    SubmissionRepository,
)
from smr.homework.application.services import HomeworkReviewSource
from smr.homework.application.use_cases import (
    AddFile,
    AssignmentRoster,
    ClearDraft,
    CopyAssignment,
    CreateAssignment,
    DeleteAssignment,
    DeleteGroupFiles,
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
from smr.roster.application.contracts import RosterApi


@final
class HomeworkProvider(Provider):
    """Everything of homework, built per update or task."""

    scope = Scope.REQUEST

    assignments = provide(SqlAlchemyAssignments, provides=AssignmentRepository)
    submissions = provide(SqlAlchemySubmissions, provides=SubmissionRepository)
    stored = provide(SqlAlchemyFiles, provides=FileRepository)
    source = provide(HomeworkReviewSource)

    use_cases = provide_all(
        AssignmentRoster,
        ClearDraft,
        CopyAssignment,
        CreateAssignment,
        DeleteAssignment,
        DeleteGroupFiles,
        DeleteStudentFiles,
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

    @provide
    def add_file(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        uow: UnitOfWork,
        settings: StorageSettings,
    ) -> AddFile:
        """Build the upload use case with the per-submission file limit.

        Args:
            assignments: AssignmentRepository - The assignments.
            submissions: SubmissionRepository - The versions.
            stored: FileRepository - The files.
            roster: RosterApi - The roster.
            files: FileStore - The disk.
            uow: UnitOfWork - The transaction.
            settings: StorageSettings - The limit.

        Returns:
            AddFile - The use case.

        """
        return AddFile(
            assignments,
            submissions,
            stored,
            roster,
            files,
            uow,
            settings.max_files_per_submission,
        )

    @provide
    def export(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        guard: AdminGuard,
        clock: Clock,
        settings: StorageSettings,
    ) -> ExportSubmissions:
        """Build the export use case writing under the data directory.

        Args:
            assignments: AssignmentRepository - The assignments.
            submissions: SubmissionRepository - The versions.
            stored: FileRepository - The files.
            roster: RosterApi - The roster.
            files: FileStore - The disk.
            guard: AdminGuard - The teachers.
            clock: Clock - The clock.
            settings: StorageSettings - Where exports go.

        Returns:
            ExportSubmissions - The use case.

        """
        return ExportSubmissions(
            assignments,
            submissions,
            stored,
            roster,
            files,
            guard,
            clock,
            settings.data_dir,
        )
