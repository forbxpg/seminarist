"""The review's view of ordinary homework: photos, PDFs, and the one-task scheme."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from operator import attrgetter
from typing import final

from smr.core.files import FileKind, FileStore, PdfBrokenError, PdfLockedError
from smr.core.files.pdf import count_pages
from smr.gradebook.application.contracts import GradebookApi
from smr.homework.application.ports import (
    AssignmentRepository,
    FileRepository,
    SubmissionRepository,
)
from smr.homework.domain import Assignment, SubmissionFile, SubmissionStatus
from smr.review.application.ports import TaskSheet, WorkPage, WorkRef
from smr.review.domain import SchemeTask
from smr.roster.application.contracts import RosterApi

_LIVE = frozenset({SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED})


@final
class HomeworkReviewSource:
    """`ReviewSource` named `homework`.

    The scheme is one task worth the assignment's maximum. Photos are one page
    each and a PDF keeps its own pages. A digest of one file is that file's
    digest; several files hash the ordered digests, so the agent can echo the
    value from the queue.
    """

    name: str = "homework"

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        files: FileStore,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._files: FileStore = files

    async def live_works(self) -> Sequence[WorkRef]:
        """List submitted versions of active groups, oldest first.

        Returns:
            Sequence[WorkRef] - The versions. Graded ones are omitted.

        """
        found: list[WorkRef] = []
        for submission in await self._submissions.submitted():
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
        """Read one submitted or graded version of an active group.

        Args:
            work_id: uuid.UUID - The version.
            lock: bool - Lock the row when true.

        Returns:
            WorkRef | None - None when missing, superseded, or the group is archived.

        """
        return await self._ref(work_id, lock=lock)

    async def sheet(self, task_ref: uuid.UUID) -> TaskSheet:
        """Read the one-task scheme and the statement.

        Args:
            task_ref: uuid.UUID - The assignment.

        Returns:
            TaskSheet - The scheme. A statement that is not a PDF stays as text.

        Raises:
            ValueError: If there is no such assignment.

        """
        assignment = await self._assignments.get(task_ref)
        if assignment is None:
            msg = "unknown assignment"
            raise ValueError(msg)
        path, pages = await self._statement(assignment)
        return TaskSheet(
            task_ref=task_ref,
            title=assignment.title,
            scheme=(SchemeTask(1, assignment.max_points),),
            max_points=assignment.max_points,
            statement_path=path,
            statement_pages=pages,
            solutions_path=None,
            solutions_pages=None,
            note="" if pages else assignment.body,
        )

    async def work_path(self, work_id: uuid.UUID) -> str:
        """Tell where the first file is stored.

        Args:
            work_id: uuid.UUID - The version.

        Returns:
            str - The FileStore path.

        Raises:
            ValueError: If the version has no file.

        """
        files = await self._stored.of_submission(work_id)
        if not files:
            msg = "unknown submission"
            raise ValueError(msg)
        return min(files, key=attrgetter("position")).path

    async def pages(self, work_id: uuid.UUID) -> Sequence[WorkPage]:
        """List photos and PDF pages in the order the student sent them.

        Args:
            work_id: uuid.UUID - The version.

        Returns:
            Sequence[WorkPage] - One entry per file.

        """
        files = sorted(
            await self._stored.of_submission(work_id),
            key=attrgetter("position"),
        )
        return [await self._page(file) for file in files]

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
        assignment = await self._assignments.get(submission.assignment_id)
        if assignment is None:
            return False
        student = await self._roster.bound_student(tg_user_id, assignment.group_id)
        return student is not None and student.student_id == submission.student_id

    async def apply_grade(
        self,
        work_id: uuid.UUID,
        total: Decimal,
        *,
        teacher: int | None,
        agent: str | None,
    ) -> None:
        """Write the total and mark the version graded, so the queue lets it go.

        Args:
            work_id: uuid.UUID - The version.
            total: Decimal - The points.
            teacher: int | None - The teacher's Telegram id.
            agent: str | None - The model's name.

        """
        submission = await self._submissions.get(work_id)
        if submission is None:
            return
        assignment = await self._assignments.get(submission.assignment_id)
        if assignment is None or assignment.item_id is None:
            return
        entry = await self._gradebook.set_entry(
            submission.student_id,
            assignment.item_id,
            total,
            excused=False,
            comment=None,
            graded_by=teacher,
            agent=agent,
        )
        await self._submissions.update(
            replace(
                submission,
                status=SubmissionStatus.GRADED,
                entry_id=entry.entry_id,
            ),
        )

    async def _ref(self, work_id: uuid.UUID, *, lock: bool) -> WorkRef | None:
        submission = await self._submissions.get(work_id, lock=lock)
        if submission is None or submission.status not in _LIVE:
            return None
        if submission.sent_at is None:
            return None
        assignment = await self._assignments.get(submission.assignment_id)
        if assignment is None:
            return None
        group = await self._roster.group(assignment.group_id)
        if group is None or not group.is_active:
            return None
        files = list(await self._stored.of_submission(submission.submission_id))
        if not files:
            return None
        student = await self._roster.student(submission.student_id)
        pages = await self.pages(submission.submission_id)
        return WorkRef(
            work_id=submission.submission_id,
            task_ref=assignment.assignment_id,
            student_ref=submission.student_id,
            version=submission.version,
            sha256=_digest(files),
            pages=sum(page.pdf_pages for page in pages),
            sent_at=submission.sent_at,
            is_late=submission.is_late,
            title=assignment.title,
            journal_no=None if student is None else student.journal_no,
        )

    async def _statement(self, assignment: Assignment) -> tuple[str, int]:
        statement = assignment.statement
        if statement is None or statement.kind is not FileKind.PDF:
            return "", 0
        count = await _pdf_pages(self._files, statement.path)
        if count == 0:
            return "", 0
        return statement.path, count

    async def _page(self, file: SubmissionFile) -> WorkPage:
        if file.kind is FileKind.PDF:
            count = await _pdf_pages(self._files, file.path)
            return WorkPage(file.path, "pdf", count or 1)
        if file.kind.is_image:
            return WorkPage(file.path, "image", 1)
        return WorkPage(file.path, "unread", 1)


def _digest(files: Sequence[SubmissionFile]) -> str:
    ordered = sorted(files, key=attrgetter("position"))
    if len(ordered) == 1:
        return ordered[0].sha256
    blob = "\n".join(file.sha256 for file in ordered).encode()
    return hashlib.sha256(blob).hexdigest()


async def _pdf_pages(files: FileStore, relative: str) -> int:
    path = files.path(relative)
    if not path.is_file():
        return 0
    data = await asyncio.to_thread(path.read_bytes)
    try:
        return count_pages(data)
    except (PdfBrokenError, PdfLockedError):
        return 1
