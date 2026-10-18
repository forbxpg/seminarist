"""БДЗ rows over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from smr.bdz.domain import Bdz, BdzSubmission, SubmissionStatus
from smr.bdz.infrastructure.models import AssignmentModel, SubmissionModel, TaskModel
from smr.review.domain import SchemeTask


@final
class SqlAlchemyAssignments:
    """Assignments and their tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, bdz: Bdz, tasks: Sequence[SchemeTask]) -> None:
        """Store a БДЗ and its scheme.

        Args:
            bdz: Bdz - The assignment.
            tasks: Sequence[SchemeTask] - Its tasks.

        """
        self._session.add(_assignment(bdz))
        for task in tasks:
            self._session.add(
                TaskModel(
                    bdz_id=bdz.bdz_id,
                    number=task.number,
                    max_points=task.max_points,
                ),
            )
        await self._session.flush()

    async def get(self, bdz_id: uuid.UUID) -> Bdz | None:
        """Read a БДЗ.

        Args:
            bdz_id: uuid.UUID - It.

        Returns:
            Bdz | None - None when unknown.

        """
        row = await self._session.get(AssignmentModel, bdz_id)
        return None if row is None else _bdz(row)

    async def tasks(self, bdz_id: uuid.UUID) -> tuple[SchemeTask, ...]:
        """Read the scheme.

        Args:
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            tuple[SchemeTask, ...] - The tasks, in order.

        """
        rows = await self._session.scalars(
            select(TaskModel)
            .where(TaskModel.bdz_id == bdz_id)
            .order_by(TaskModel.number),
        )
        return tuple(SchemeTask(row.number, row.max_points) for row in rows)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Bdz]:
        """List a group's БДЗ, newest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Bdz] - The assignments.

        """
        rows = await self._session.scalars(
            select(AssignmentModel)
            .where(AssignmentModel.group_id == group_id)
            .order_by(AssignmentModel.created_at.desc()),
        )
        return [_bdz(row) for row in rows]

    async def save_deadline(self, bdz: Bdz) -> None:
        """Store a new deadline.

        Args:
            bdz: Bdz - The assignment with the new deadline.

        """
        row = await self._session.get(AssignmentModel, bdz.bdz_id)
        if row is not None:
            row.deadline = bdz.deadline

    async def delete(self, bdz_id: uuid.UUID) -> Bdz | None:
        """Delete a БДЗ. Submissions cascade.

        Args:
            bdz_id: uuid.UUID - It.

        Returns:
            Bdz | None - What was deleted.

        """
        found = await self.get(bdz_id)
        if found is None:
            return None
        _ = await self._session.execute(
            delete(AssignmentModel).where(AssignmentModel.bdz_id == bdz_id),
        )
        return found


@final
class SqlAlchemySubmissions:
    """Students' versions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, submission: BdzSubmission) -> None:
        """Store a version.

        Args:
            submission: BdzSubmission - It.

        """
        self._session.add(_submission(submission))
        await self._session.flush()

    async def get(
        self,
        submission_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> BdzSubmission | None:
        """Read a version.

        Args:
            submission_id: uuid.UUID - It.
            lock: bool - Lock the row when true.

        Returns:
            BdzSubmission | None - None when unknown.

        """
        query = select(SubmissionModel).where(
            SubmissionModel.submission_id == submission_id,
        )
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        return None if row is None else _domain(row)

    async def live(
        self,
        bdz_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> BdzSubmission | None:
        """Read the live version of a student.

        Args:
            bdz_id: uuid.UUID - The БДЗ.
            student_id: uuid.UUID - The student.
            lock: bool - Lock the row when true.

        Returns:
            BdzSubmission | None - None when they have not sent one.

        """
        query = select(SubmissionModel).where(
            SubmissionModel.bdz_id == bdz_id,
            SubmissionModel.student_id == student_id,
            SubmissionModel.status == SubmissionStatus.LIVE.value,
        )
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        return None if row is None else _domain(row)

    async def live_all(self) -> Sequence[BdzSubmission]:
        """List every live version, oldest first.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        rows = await self._session.scalars(
            select(SubmissionModel)
            .where(SubmissionModel.status == SubmissionStatus.LIVE.value)
            .order_by(SubmissionModel.sent_at),
        )
        return [_domain(row) for row in rows]

    async def of_bdz(self, bdz_id: uuid.UUID) -> Sequence[BdzSubmission]:
        """List every version of a БДЗ.

        Args:
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        rows = await self._session.scalars(
            select(SubmissionModel).where(SubmissionModel.bdz_id == bdz_id),
        )
        return [_domain(row) for row in rows]

    async def of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[BdzSubmission]:
        """List every version of these students.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        if not student_ids:
            return []
        rows = await self._session.scalars(
            select(SubmissionModel).where(SubmissionModel.student_id.in_(student_ids)),
        )
        return [_domain(row) for row in rows]

    async def next_version(self, bdz_id: uuid.UUID, student_id: uuid.UUID) -> int:
        """Tell the next version number.

        Args:
            bdz_id: uuid.UUID - The БДЗ.
            student_id: uuid.UUID - The student.

        Returns:
            int - One more than the highest version, or 1.

        """
        current = await self._session.scalar(
            select(func.max(SubmissionModel.version)).where(
                SubmissionModel.bdz_id == bdz_id,
                SubmissionModel.student_id == student_id,
            ),
        )
        return 1 if current is None else int(current) + 1

    async def supersede(self, submission_id: uuid.UUID) -> None:
        """Mark a version superseded.

        Args:
            submission_id: uuid.UUID - It.

        """
        row = await self._session.get(SubmissionModel, submission_id)
        if row is not None:
            row.status = SubmissionStatus.SUPERSEDED.value


def _assignment(bdz: Bdz) -> AssignmentModel:
    return AssignmentModel(
        bdz_id=bdz.bdz_id,
        group_id=bdz.group_id,
        work_type_id=bdz.work_type_id,
        item_id=bdz.item_id,
        title=bdz.title,
        deadline=bdz.deadline,
        max_points=bdz.max_points,
        statement_path=bdz.statement_path,
        statement_tg_file_id=bdz.statement_tg_file_id,
        statement_pages=bdz.statement_pages,
        solutions_path=bdz.solutions_path,
        solutions_tg_file_id=bdz.solutions_tg_file_id,
        solutions_pages=bdz.solutions_pages,
        created_at=bdz.created_at,
    )


def _bdz(row: AssignmentModel) -> Bdz:
    return Bdz(
        bdz_id=row.bdz_id,
        group_id=row.group_id,
        work_type_id=row.work_type_id,
        item_id=row.item_id,
        title=row.title,
        deadline=row.deadline,
        max_points=row.max_points,
        statement_path=row.statement_path,
        statement_tg_file_id=row.statement_tg_file_id,
        statement_pages=row.statement_pages,
        solutions_path=row.solutions_path,
        solutions_tg_file_id=row.solutions_tg_file_id,
        solutions_pages=row.solutions_pages,
        created_at=row.created_at,
    )


def _submission(submission: BdzSubmission) -> SubmissionModel:
    return SubmissionModel(
        submission_id=submission.submission_id,
        bdz_id=submission.bdz_id,
        student_id=submission.student_id,
        version=submission.version,
        status=submission.status.value,
        path=submission.path,
        tg_file_id=submission.tg_file_id,
        tg_file_unique_id=submission.tg_file_unique_id,
        size=submission.size,
        sha256=submission.sha256,
        pages=submission.pages,
        sent_at=submission.sent_at,
        is_late=submission.is_late,
    )


def _domain(row: SubmissionModel) -> BdzSubmission:
    return BdzSubmission(
        submission_id=row.submission_id,
        bdz_id=row.bdz_id,
        student_id=row.student_id,
        version=row.version,
        status=SubmissionStatus(row.status),
        path=row.path,
        tg_file_id=row.tg_file_id,
        tg_file_unique_id=row.tg_file_unique_id,
        size=row.size,
        sha256=row.sha256,
        pages=row.pages,
        sent_at=row.sent_at,
        is_late=row.is_late,
    )
