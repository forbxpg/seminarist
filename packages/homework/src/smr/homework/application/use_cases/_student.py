"""A student's side: their assignments, a draft of files, submitting."""

from __future__ import annotations

import dataclasses
import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from operator import attrgetter
from typing import final

from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.core.files import FileKind, FileStore
from smr.gradebook.application.contracts import GradebookApi
from smr.homework.application.ports import (
    AssignmentRepository,
    FileRepository,
    SubmissionRepository,
)
from smr.homework.domain import (
    Assignment,
    DraftEmptyError,
    Submission,
    SubmissionClosedError,
    SubmissionFile,
    SubmissionStatus,
    TooManyFilesError,
)
from smr.review.application.contracts import ReviewApi
from smr.review.application.use_cases import FlagUnreadable
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import StudentNotFoundError

from ._common import assignment_of, open_group, student_of
from ._upload import Upload

STUDENT_KINDS: frozenset[FileKind] = frozenset(FileKind)
_UNREADABLE = {
    FileKind.DOCX: "Файл DOCX прочитать нельзя. Пришлите PDF или фото страниц.",
    FileKind.HEIC: "Формат HEIC показать нельзя. Пришлите JPEG, PNG или PDF.",
}


@dataclass(frozen=True, slots=True)
class StudentWork:
    """An assignment as its student sees it.

    Attributes:
        assignment: Assignment - The assignment.
        live: Submission | None - Their submitted or graded version.
        live_files: int - Files in it.
        draft_files: int - Files waiting in the draft.
        points: Decimal | None - Their grade, once graded.
        comment: str | None - The teacher's note.

    """

    assignment: Assignment
    live: Submission | None
    live_files: int
    draft_files: int
    points: Decimal | None
    comment: str | None


@final
class StudentAssignments:
    """A student's assignments with where each stands."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook

    async def __call__(self, tg_user_id: int, group_id: uuid.UUID) -> list[StudentWork]:
        """List them.

        Args:
            tg_user_id: int - The asking account.
            group_id: uuid.UUID - The group.

        Returns:
            list[StudentWork] - The latest deadline first.

        Raises:
            StudentNotFoundError: If the account holds no approved row of the group.

        """
        student = await self._roster.bound_student(tg_user_id, group_id)
        if student is None:
            raise StudentNotFoundError
        return [
            await work_of(
                assignment,
                student.student_id,
                self._submissions,
                self._stored,
                self._gradebook,
            )
            for assignment in await self._assignments.of_group(group_id)
        ]


async def work_of(
    assignment: Assignment,
    student_id: uuid.UUID,
    submissions: SubmissionRepository,
    stored: FileRepository,
    gradebook: GradebookApi,
) -> StudentWork:
    """Gather where a student's work on an assignment stands.

    Args:
        assignment: Assignment - The assignment.
        student_id: uuid.UUID - The student.
        submissions: SubmissionRepository - The versions.
        stored: FileRepository - The files.
        gradebook: GradebookApi - The ledger.

    Returns:
        StudentWork - The state.

    """
    live = await submissions.live(assignment.assignment_id, student_id)
    draft = await submissions.draft(assignment.assignment_id, student_id)
    entry = None
    if live is not None and live.entry_id is not None:
        entry = await gradebook.entry(live.entry_id)
    return StudentWork(
        assignment=assignment,
        live=live,
        live_files=0
        if live is None
        else len(await stored.of_submission(live.submission_id)),
        draft_files=0
        if draft is None
        else len(await stored.of_submission(draft.submission_id)),
        points=None if entry is None else entry.points,
        comment=None if entry is None else entry.comment,
    )


@final
class AddFile:
    """A file joins the student's draft of an assignment."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        uow: UnitOfWork,
        max_files: int,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._max_files: int = max_files

    async def __call__(
        self,
        tg_user_id: int,
        assignment_id: uuid.UUID,
        upload: Upload,
    ) -> int:
        """Add it.

        Args:
            tg_user_id: int - The sending account.
            assignment_id: uuid.UUID - The assignment.
            upload: Upload - The file.

        Returns:
            int - How many files the draft now holds.

        Raises:
            SubmissionClosedError: If the work is already graded.
            TooManyFilesError: If the draft is full.

        """
        async with self._uow:
            assignment = await assignment_of(self._assignments, assignment_id)
            _ = await open_group(self._roster, assignment.group_id)
            student = await student_of(self._roster, tg_user_id, assignment)
            live = await self._submissions.live(assignment_id, student.student_id)
            if live is not None and live.status is SubmissionStatus.GRADED:
                raise SubmissionClosedError
            draft = await self._submissions.draft(assignment_id, student.student_id)
            if draft is None:
                draft = Submission(
                    submission_id=uuid.uuid4(),
                    assignment_id=assignment_id,
                    student_id=student.student_id,
                    version=await self._submissions.next_version(
                        assignment_id,
                        student.student_id,
                    ),
                    status=SubmissionStatus.DRAFT,
                    sent_at=None,
                    is_late=False,
                    entry_id=None,
                )
                await self._submissions.add(draft)
            present = await self._stored.of_submission(draft.submission_id)
            if len(present) >= self._max_files:
                raise TooManyFilesError
            saved = await self._files.save(
                upload.data,
                accepted=STUDENT_KINDS,
                now=upload.sent_at,
            )
            await self._stored.add(
                SubmissionFile(
                    file_id=uuid.uuid4(),
                    submission_id=draft.submission_id,
                    tg_file_id=upload.tg_file_id,
                    tg_file_unique_id=upload.tg_file_unique_id,
                    path=saved.relative_path,
                    kind=saved.kind,
                    size=saved.size,
                    sha256=saved.sha256,
                    position=len(present) + 1,
                    sent_at=upload.sent_at,
                ),
            )
            await self._uow.commit()
        return len(present) + 1


@final
class ClearDraft:
    """The student throws away the draft and its files."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        uow: UnitOfWork,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._files: FileStore = files
        self._uow: UnitOfWork = uow

    async def __call__(self, tg_user_id: int, assignment_id: uuid.UUID) -> None:
        """Throw it away.

        Args:
            tg_user_id: int - The account.
            assignment_id: uuid.UUID - The assignment.

        """
        async with self._uow:
            assignment = await assignment_of(self._assignments, assignment_id)
            student = await student_of(self._roster, tg_user_id, assignment)
            draft = await self._submissions.draft(assignment_id, student.student_id)
            if draft is None:
                return
            paths = await self._stored.delete_of_submission(draft.submission_id)
            await self._submissions.delete(draft.submission_id)
            await self._uow.commit()
        for path in paths:
            await self._files.delete(path)


@final
class Submit:
    """The draft becomes the work the teacher will grade."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        uow: UnitOfWork,
        audit: AuditLog,
        clock: Clock,
        reviews: ReviewApi,
        flags: FlagUnreadable,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._clock: Clock = clock
        self._reviews: ReviewApi = reviews
        self._flags: FlagUnreadable = flags

    async def __call__(self, tg_user_id: int, assignment_id: uuid.UUID) -> Submission:
        """Submit it.

        Args:
            tg_user_id: int - The account.
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Submission - The submitted version.

        Raises:
            DraftEmptyError: If the draft holds no file.
            SubmissionClosedError: If the work is already graded.

        """
        async with self._uow:
            assignment = await assignment_of(self._assignments, assignment_id)
            _ = await open_group(self._roster, assignment.group_id)
            student = await student_of(self._roster, tg_user_id, assignment)
            draft = await self._submissions.draft(assignment_id, student.student_id)
            files = (
                []
                if draft is None
                else list(await self._stored.of_submission(draft.submission_id))
            )
            if draft is None or not files:
                raise DraftEmptyError
            live = await self._submissions.live(
                assignment_id,
                student.student_id,
                lock=True,
            )
            superseded: list[str] = []
            if live is not None:
                if live.status is SubmissionStatus.GRADED:
                    raise SubmissionClosedError
                await self._reviews.void("homework", live.submission_id)
                superseded = list(
                    await self._stored.delete_of_submission(live.submission_id),
                )
                await self._submissions.update(
                    dataclasses.replace(live, status=SubmissionStatus.SUPERSEDED),
                )
            sent_at = max(file.sent_at for file in files)
            submitted = dataclasses.replace(
                draft,
                status=SubmissionStatus.SUBMITTED,
                sent_at=sent_at,
                is_late=sent_at > assignment.deadline,
            )
            await self._submissions.update(submitted)
            explanation = _unreadable(files)
            if explanation is not None:
                await self._flags(
                    "homework",
                    submitted.submission_id,
                    _digest(files),
                    assignment.assignment_id,
                    student.student_id,
                    assignment.title,
                    assignment.max_points,
                    explanation,
                )
            await self._audit.record(
                AuditEntry(
                    ActorKind.STUDENT,
                    str(student.student_id),
                    "homework.submitted",
                    "submission",
                    str(submitted.submission_id),
                    after={"version": submitted.version, "late": submitted.is_late},
                ),
            )
            await self._uow.commit()
        for path in superseded:
            await self._files.delete(path)
        return submitted


@final
class MyWork:
    """A student's own work on an assignment, with its files."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook

    async def __call__(self, tg_user_id: int, assignment_id: uuid.UUID) -> StudentWork:
        """Read it.

        Args:
            tg_user_id: int - The account.
            assignment_id: uuid.UUID - The assignment.

        Returns:
            StudentWork - Where it stands.

        """
        assignment = await assignment_of(self._assignments, assignment_id)
        student = await student_of(self._roster, tg_user_id, assignment)
        return await work_of(
            assignment,
            student.student_id,
            self._submissions,
            self._stored,
            self._gradebook,
        )


def _unreadable(files: list[SubmissionFile]) -> str | None:
    reasons = [
        text
        for kind, text in _UNREADABLE.items()
        if any(file.kind is kind for file in files)
    ]
    if not reasons:
        return None
    return " ".join(reasons)


def _digest(files: list[SubmissionFile]) -> str:
    ordered = sorted(files, key=attrgetter("position"))
    if len(ordered) == 1:
        return ordered[0].sha256
    blob = "\n".join(file.sha256 for file in ordered).encode()
    return hashlib.sha256(blob).hexdigest()
