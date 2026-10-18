"""The БДЗ's repositories, use cases and review source."""

from __future__ import annotations

from collections.abc import Sequence
from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.bdz.application.ports import AssignmentRepository, SubmissionRepository
from smr.bdz.application.services import BdzReviewSource
from smr.bdz.application.use_cases import (
    BdzLimits,
    BdzRoster,
    BdzStatement,
    CreateBdz,
    DeleteBdz,
    DeleteGroupBdzFiles,
    DeleteStudentBdzFiles,
    ExportBdz,
    ListBdz,
    SendBdz,
    StudentBdzList,
    UpdateBdzDeadline,
)
from smr.bdz.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemySubmissions,
)
from smr.core.access import AdminGuard
from smr.core.clock import Clock
from smr.core.config import StorageSettings
from smr.core.files import FileStore
from smr.review.application.contracts import ReviewApi
from smr.review.application.ports import ReviewSource
from smr.roster.application.contracts import RosterApi


@final
class BdzProvider(Provider):
    """Everything of a БДЗ, including the source the review reads."""

    scope = Scope.REQUEST

    assignments = provide(SqlAlchemyAssignments, provides=AssignmentRepository)
    submissions = provide(SqlAlchemySubmissions, provides=SubmissionRepository)
    source = provide(BdzReviewSource)

    use_cases = provide_all(
        BdzStatement,
        CreateBdz,
        BdzRoster,
        DeleteBdz,
        DeleteGroupBdzFiles,
        DeleteStudentBdzFiles,
        ListBdz,
        SendBdz,
        StudentBdzList,
        UpdateBdzDeadline,
    )

    @provide
    def review_sources(self, source: BdzReviewSource) -> Sequence[ReviewSource]:
        """Give the review its only source for now.

        Args:
            source: BdzReviewSource - The БДЗ source.

        Returns:
            Sequence[ReviewSource] - That one source.

        """
        return (source,)

    @provide
    def limits(self, storage: StorageSettings) -> BdzLimits:
        """Tell how many pages a БДЗ PDF may have.

        Args:
            storage: StorageSettings - The setting.

        Returns:
            BdzLimits - The page cap.

        """
        return BdzLimits(storage.bdz_max_pages)

    @provide
    def export(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        reviews: ReviewApi,
        files: FileStore,
        guard: AdminGuard,
        clock: Clock,
        storage: StorageSettings,
    ) -> ExportBdz:
        """Build the export that writes under the data directory.

        Args:
            assignments: AssignmentRepository - The assignments.
            submissions: SubmissionRepository - The versions.
            roster: RosterApi - The roster.
            reviews: ReviewApi - The verdicts.
            files: FileStore - The disk.
            guard: AdminGuard - The teachers.
            clock: Clock - The clock.
            storage: StorageSettings - Where exports go.

        Returns:
            ExportBdz - The use case.

        """
        return ExportBdz(
            assignments,
            submissions,
            roster,
            reviews,
            files,
            guard,
            clock,
            storage.data_dir,
        )
