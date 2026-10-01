"""The teacher's side: the queue of work to grade, its files, grading."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from smr.homework.domain import (
    Submission,
    SubmissionNotFoundError,
    SubmissionStatus,
)
from smr.roster.domain import StudentNotFoundError

from ._common import assignment_of

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal

    from smr.core.access import AdminGuard
    from smr.core.database import UnitOfWork
    from smr.gradebook.application.contracts import GradebookApi
    from smr.homework.application.ports import (
        AssignmentRepository,
        FileRepository,
        SubmissionRepository,
    )
    from smr.homework.domain import Assignment, SubmissionFile
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Student


@dataclass(frozen=True, slots=True)
class Review:
    """A version of a student's work, ready to be graded.

    Attributes:
        submission: Submission - The version.
        assignment: Assignment - Its assignment.
        student: Student - Its author.
        files: Sequence[SubmissionFile] - Its files, in order.

    """

    submission: Submission
    assignment: Assignment
    student: Student
    files: Sequence[SubmissionFile]


@final
class ReviewQueue:
    """A group's submitted, ungraded work, the earliest sent first."""

    def __init__(
        self,
        submissions: SubmissionRepository,
        guard: AdminGuard,
    ) -> None:
        self._submissions: SubmissionRepository = submissions
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> Sequence[Submission]:
        """List it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Submission] - The queue.

        """
        self._guard.require(actor)
        return await self._submissions.waiting(group_id)


@final
class OpenSubmission:
    """A version with its assignment, author and files, for the teacher."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, submission_id: uuid.UUID) -> Review:
        """Open it.

        Args:
            actor: int - Teacher's Telegram id.
            submission_id: uuid.UUID - The version.

        Returns:
            Review - Everything to grade it.

        Raises:
            SubmissionNotFoundError: If there is no such version.
            StudentNotFoundError: If its author is gone.

        """
        self._guard.require(actor)
        submission = await self._submissions.get(submission_id)
        if submission is None:
            raise SubmissionNotFoundError
        student = await self._roster.student(submission.student_id)
        if student is None:
            raise StudentNotFoundError
        return Review(
            submission=submission,
            assignment=await assignment_of(self._assignments, submission.assignment_id),
            student=student,
            files=await self._stored.of_submission(submission_id),
        )


@final
class GradeSubmission:
    """Points for the live version; regrading replaces them."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        submission_id: uuid.UUID,
        points: Decimal,
        comment: str | None,
    ) -> tuple[Submission, Student]:
        """Grade it.

        Args:
            actor: int - Teacher's Telegram id.
            submission_id: uuid.UUID - The version.
            points: Decimal - Its points.
            comment: str | None - A note for the student.

        Returns:
            tuple[Submission, Student] - The graded version and its author, to tell.

        Raises:
            SubmissionNotFoundError: If there is no such version, or it is not live.
            StudentNotFoundError: If its author is gone.

        """
        self._guard.require(actor)
        async with self._uow:
            submission = await self._submissions.get(submission_id, lock=True)
            live_states = {SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED}
            if submission is None or submission.status not in live_states:
                raise SubmissionNotFoundError
            assignment = await assignment_of(
                self._assignments,
                submission.assignment_id,
            )
            student = await self._roster.student(submission.student_id)
            if student is None or assignment.item_id is None:
                raise StudentNotFoundError
            entry = await self._gradebook.set_entry(
                submission.student_id,
                assignment.item_id,
                points,
                excused=False,
                comment=" ".join(comment.split()) if comment else None,
                graded_by=actor,
            )
            graded = dataclasses.replace(
                submission,
                status=SubmissionStatus.GRADED,
                entry_id=entry.entry_id,
            )
            await self._submissions.update(graded)
            await self._uow.commit()
        return graded, student
