"""БДЗ files leave the disk with the student or the group."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from smr.bdz.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemySubmissions,
)
from smr.core.database import UnitOfWork
from smr.core.files import FileStore
from smr.review.application.contracts import ReviewApi


@final
class DeleteStudentBdzFiles:
    """Forget a student's PDFs and the verdicts about them."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        submissions: SqlAlchemySubmissions,
        reviews: ReviewApi,
        files: FileStore,
        uow: UnitOfWork,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._submissions: SqlAlchemySubmissions = submissions
        self._reviews: ReviewApi = reviews
        self._files: FileStore = files
        self._uow: UnitOfWork = uow

    async def __call__(self, student_ids: Sequence[uuid.UUID]) -> int:
        """Delete them.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            int - How many files were deleted.

        """
        async with self._uow:
            versions = await self._submissions.of_students(student_ids)
            work_ids = [row.submission_id for row in versions]
            await self._reviews.forget_works("bdz", work_ids)
            await self._uow.commit()
        for row in versions:
            await self._files.delete(row.path)
        return len(versions)


@final
class DeleteGroupBdzFiles:
    """Before a group is purged, its БДЗ files and verdicts leave."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        submissions: SqlAlchemySubmissions,
        reviews: ReviewApi,
        files: FileStore,
        uow: UnitOfWork,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._submissions: SqlAlchemySubmissions = submissions
        self._reviews: ReviewApi = reviews
        self._files: FileStore = files
        self._uow: UnitOfWork = uow

    async def __call__(self, group_id: uuid.UUID) -> int:
        """Delete them.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            int - How many files were deleted.

        """
        async with self._uow:
            assignments = await self._assignments.of_group(group_id)
            paths = [item.statement_path for item in assignments]
            paths.extend(item.solutions_path for item in assignments)
            ids: list[uuid.UUID] = []
            for item in assignments:
                versions = await self._submissions.of_bdz(item.bdz_id)
                ids.extend(row.submission_id for row in versions)
                paths.extend(row.path for row in versions)
            await self._reviews.forget_works("bdz", ids)
            await self._uow.commit()
        for path in paths:
            await self._files.delete(path)
        return len(paths)
