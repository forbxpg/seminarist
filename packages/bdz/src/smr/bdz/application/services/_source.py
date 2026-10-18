"""The review's view of a БДЗ: live PDFs, the scheme, and the ledger."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import final

from smr.bdz.application.ports import AssignmentRepository, SubmissionRepository
from smr.bdz.domain import SubmissionStatus
from smr.gradebook.application.contracts import GradebookApi
from smr.review.application.ports import TaskSheet, WorkRef
from smr.roster.application.contracts import RosterApi


@final
class BdzReviewSource:
    """`ReviewSource` named `bdz`."""

    name: str = "bdz"

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook

    async def live_works(self) -> Sequence[WorkRef]:
        """List live versions of active groups, oldest first.

        Returns:
            Sequence[WorkRef] - The versions.

        """
        found: list[WorkRef] = []
        for submission in await self._submissions.live_all():
            work = await self._ref(submission.submission_id, lock=False)
            if work is not None:
                found.append(work)
        return found

    async def work(
        self,
        work_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> WorkRef | None:
        """Read one live version of an active group.

        Args:
            work_id: uuid.UUID - The version.
            lock: bool - Lock the row when true.

        Returns:
            WorkRef | None - None when missing, not live, or the group is archived.

        """
        return await self._ref(work_id, lock=lock)

    async def sheet(self, task_ref: uuid.UUID) -> TaskSheet:
        """Read the scheme and the files.

        Args:
            task_ref: uuid.UUID - The БДЗ.

        Returns:
            TaskSheet - The scheme.

        Raises:
            ValueError: If there is no such БДЗ.

        """
        bdz = await self._assignments.get(task_ref)
        tasks = await self._assignments.tasks(task_ref)
        if bdz is None:
            msg = "unknown bdz"
            raise ValueError(msg)
        return TaskSheet(
            task_ref=task_ref,
            title=bdz.title,
            scheme=tasks,
            max_points=bdz.max_points,
            statement_path=bdz.statement_path,
            statement_pages=bdz.statement_pages,
            solutions_path=bdz.solutions_path,
            solutions_pages=bdz.solutions_pages,
        )

    async def work_path(self, work_id: uuid.UUID) -> str:
        """Tell where the PDF is stored.

        Args:
            work_id: uuid.UUID - The version.

        Returns:
            str - The FileStore path.

        Raises:
            ValueError: If there is no such version.

        """
        submission = await self._submissions.get(work_id)
        if submission is None:
            msg = "unknown submission"
            raise ValueError(msg)
        return submission.path

    async def belongs_to(self, work_id: uuid.UUID, tg_user_id: int) -> bool:
        """Tell whether the account owns the version.

        Args:
            work_id: uuid.UUID - The version.
            tg_user_id: int - The account.

        Returns:
            bool - True for the approved row of the group.

        """
        submission = await self._submissions.get(work_id)
        if submission is None:
            return False
        bdz = await self._assignments.get(submission.bdz_id)
        if bdz is None:
            return False
        student = await self._roster.bound_student(tg_user_id, bdz.group_id)
        return student is not None and student.student_id == submission.student_id

    async def apply_grade(
        self,
        work_id: uuid.UUID,
        total: Decimal,
        *,
        teacher: int | None,
        agent: str | None,
    ) -> None:
        """Write the total into the ledger.

        Args:
            work_id: uuid.UUID - The version.
            total: Decimal - The points.
            teacher: int | None - The teacher's Telegram id.
            agent: str | None - The model's name.

        """
        submission = await self._submissions.get(work_id)
        if submission is None:
            return
        bdz = await self._assignments.get(submission.bdz_id)
        if bdz is None or bdz.item_id is None:
            return
        _ = await self._gradebook.set_entry(
            submission.student_id,
            bdz.item_id,
            total,
            excused=False,
            comment=None,
            graded_by=teacher,
            agent=agent,
        )

    async def _ref(self, work_id: uuid.UUID, *, lock: bool) -> WorkRef | None:
        submission = await self._submissions.get(work_id, lock=lock)
        if submission is None or submission.status is not SubmissionStatus.LIVE:
            return None
        bdz = await self._assignments.get(submission.bdz_id)
        if bdz is None:
            return None
        group = await self._roster.group(bdz.group_id)
        if group is None or not group.is_active:
            return None
        return WorkRef(
            work_id=submission.submission_id,
            task_ref=bdz.bdz_id,
            student_ref=submission.student_id,
            version=submission.version,
            sha256=submission.sha256,
            pages=submission.pages,
            sent_at=submission.sent_at,
            is_late=submission.is_late,
            title=bdz.title,
        )
