"""The files of students' work over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from smr.core.files import FileKind
from smr.homework.domain import SubmissionFile
from smr.homework.infrastructure.models import (
    AssignmentModel,
    FileModel,
    SubmissionModel,
)

_Row = FileModel


@final
class SqlAlchemyFiles:
    """`FileRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, file: SubmissionFile) -> None:
        """Add a file.

        Args:
            file: SubmissionFile - It.

        """
        self._session.add(
            _Row(
                id=file.file_id,
                submission_id=file.submission_id,
                tg_file_id=file.tg_file_id,
                tg_file_unique_id=file.tg_file_unique_id,
                path=file.path,
                kind=file.kind.value,
                size=file.size,
                sha256=file.sha256,
                position=file.position,
                sent_at=file.sent_at,
            ),
        )
        await self._session.flush()

    async def of_submission(self, submission_id: uuid.UUID) -> Sequence[SubmissionFile]:
        """List a version's files in order.

        Args:
            submission_id: uuid.UUID - The version.

        Returns:
            Sequence[SubmissionFile] - Its files.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.submission_id == submission_id)
            .order_by(_Row.position),
        )
        return [_domain(row) for row in rows]

    async def paths_of_assignment(self, assignment_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of an assignment's files, its statement included.

        Args:
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Sequence[str] - The paths.

        """
        files = await self._session.scalars(
            select(_Row.path)
            .join(SubmissionModel, SubmissionModel.id == _Row.submission_id)
            .where(SubmissionModel.assignment_id == assignment_id),
        )
        statement = await self._session.scalar(
            select(AssignmentModel.statement_path).where(
                AssignmentModel.id == assignment_id,
            ),
        )
        return [*files, *([statement] if statement else [])]

    async def delete_of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[str]:
        """Delete the rows of students' files.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[str] - The stored paths of the deleted rows.

        """
        if not student_ids:
            return []
        owned = select(SubmissionModel.id).where(
            SubmissionModel.student_id.in_(student_ids),
        )
        deleted = await self._session.scalars(
            delete(_Row).where(_Row.submission_id.in_(owned)).returning(_Row.path),
        )
        return list(deleted)

    async def delete_of_submission(self, submission_id: uuid.UUID) -> Sequence[str]:
        """Delete the rows of a version's files.

        Args:
            submission_id: uuid.UUID - The version.

        Returns:
            Sequence[str] - The stored paths of the deleted rows.

        """
        deleted = await self._session.scalars(
            delete(_Row)
            .where(_Row.submission_id == submission_id)
            .returning(_Row.path),
        )
        return list(deleted)

    async def paths_of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[str]:
        """List the stored paths of students' files.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[str] - The paths.

        """
        rows = await self._session.scalars(
            select(_Row.path)
            .join(SubmissionModel, SubmissionModel.id == _Row.submission_id)
            .where(SubmissionModel.student_id.in_(student_ids)),
        )
        return list(rows)

    async def paths_of_group(self, group_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of a group's files, statements included.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[str] - The paths.

        """
        files = await self._session.scalars(
            select(_Row.path)
            .join(SubmissionModel, SubmissionModel.id == _Row.submission_id)
            .join(AssignmentModel, AssignmentModel.id == SubmissionModel.assignment_id)
            .where(AssignmentModel.group_id == group_id),
        )
        statements = await self._session.scalars(
            select(AssignmentModel.statement_path).where(
                AssignmentModel.group_id == group_id,
                AssignmentModel.statement_path.is_not(None),
            ),
        )
        return [*files, *(path for path in statements if path)]


def _domain(row: FileModel) -> SubmissionFile:
    return SubmissionFile(
        file_id=row.id,
        submission_id=row.submission_id,
        tg_file_id=row.tg_file_id,
        tg_file_unique_id=row.tg_file_unique_id,
        path=row.path,
        kind=FileKind(row.kind),
        size=row.size,
        sha256=row.sha256,
        position=row.position,
        sent_at=row.sent_at,
    )
