"""The versions of students' work over the session."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import delete, func, select, update

from smr.homework.domain import Submission, SubmissionStatus
from smr.homework.infrastructure.models import AssignmentModel, SubmissionModel

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

_Row = SubmissionModel
_LIVE = (SubmissionStatus.SUBMITTED.value, SubmissionStatus.GRADED.value)


@final
class SqlAlchemySubmissions:
    """`SubmissionRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, submission: Submission) -> None:
        """Add a version.

        Args:
            submission: Submission - It.

        """
        self._session.add(
            _Row(
                id=submission.submission_id,
                assignment_id=submission.assignment_id,
                student_id=submission.student_id,
                version=submission.version,
                status=submission.status.value,
                sent_at=submission.sent_at,
                is_late=submission.is_late,
                entry_id=submission.entry_id,
            ),
        )
        await self._session.flush()

    async def get(
        self,
        submission_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Submission | None:
        """Read a version.

        Args:
            submission_id: uuid.UUID - It.
            lock: bool - Lock the row until the transaction ends.

        Returns:
            Submission | None - It, or None.

        """
        query = select(_Row).where(_Row.id == submission_id)
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(
            query.execution_options(populate_existing=True),
        )
        return None if row is None else _domain(row)

    async def draft(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> Submission | None:
        """Find a student's draft.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.

        Returns:
            Submission | None - The draft, or None.

        """
        row = await self._session.scalar(
            select(_Row)
            .where(
                _Row.assignment_id == assignment_id,
                _Row.student_id == student_id,
                _Row.status == SubmissionStatus.DRAFT.value,
            )
            .execution_options(populate_existing=True),
        )
        return None if row is None else _domain(row)

    async def live(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Submission | None:
        """Find a student's submitted or graded version.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.
            lock: bool - Lock the row until the transaction ends.

        Returns:
            Submission | None - It, or None.

        """
        query = select(_Row).where(
            _Row.assignment_id == assignment_id,
            _Row.student_id == student_id,
            _Row.status.in_(_LIVE),
        )
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(
            query.execution_options(populate_existing=True),
        )
        return None if row is None else _domain(row)

    async def next_version(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> int:
        """Tell the number of a student's next version.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.

        Returns:
            int - One more than the highest so far, 1 for the first.

        """
        highest = await self._session.scalar(
            select(func.max(_Row.version)).where(
                _Row.assignment_id == assignment_id,
                _Row.student_id == student_id,
            ),
        )
        return (highest or 0) + 1

    async def live_of_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> Sequence[Submission]:
        """List the live versions of an assignment.

        Args:
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Sequence[Submission] - Submitted or graded versions.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.assignment_id == assignment_id, _Row.status.in_(_LIVE))
            .order_by(_Row.sent_at),
        )
        return [_domain(row) for row in rows]

    async def waiting(self, group_id: uuid.UUID) -> Sequence[Submission]:
        """List a group's submitted, ungraded versions, the earliest sent first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Submission] - The queue.

        """
        rows = await self._session.scalars(
            select(_Row)
            .join(AssignmentModel, AssignmentModel.id == _Row.assignment_id)
            .where(
                AssignmentModel.group_id == group_id,
                _Row.status == SubmissionStatus.SUBMITTED.value,
            )
            .order_by(_Row.sent_at),
        )
        return [_domain(row) for row in rows]

    async def update(self, submission: Submission) -> None:
        """Store a changed version.

        Args:
            submission: Submission - It, changed.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == submission.submission_id)
            .values(
                status=submission.status.value,
                sent_at=submission.sent_at,
                is_late=submission.is_late,
                entry_id=submission.entry_id,
            ),
        )

    async def delete(self, submission_id: uuid.UUID) -> None:
        """Delete a version with its files' rows.

        Args:
            submission_id: uuid.UUID - It.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == submission_id))


def _domain(row: SubmissionModel) -> Submission:
    return Submission(
        submission_id=row.id,
        assignment_id=row.assignment_id,
        student_id=row.student_id,
        version=row.version,
        status=SubmissionStatus(row.status),
        sent_at=row.sent_at,
        is_late=row.is_late,
        entry_id=row.entry_id,
    )
