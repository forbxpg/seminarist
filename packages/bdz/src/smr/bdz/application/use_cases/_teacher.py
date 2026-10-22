"""The teacher publishes a БДЗ and changes its deadline."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import final

from smr.bdz.application.ports import AssignmentRepository, SubmissionRepository
from smr.bdz.domain import (
    Bdz,
    BdzDraft,
    BdzNotFoundError,
    BdzSubmission,
    InvalidSchemeError,
    SubmissionStatus,
    WorkTypeNotProportionalError,
)
from smr.core.access import AdminGuard
from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.core.files import FileStore, StoredFile
from smr.gradebook.application.contracts import GradebookApi
from smr.gradebook.domain import ScoringMode, WorkTypeNotFoundError
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.review.application.contracts import ReviewApi
from smr.review.domain import VerdictStatus
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import Group, GroupArchivedError, GroupNotFoundError, Student

from ._limits import BdzLimits
from ._pdf import store_pdf
from ._upload import Upload

_TITLE_LIMIT = 120


@dataclass(frozen=True, slots=True)
class BdzSummary:
    """A БДЗ on the teacher's list.

    Attributes:
        bdz: Bdz - The assignment.
        sent: int - Students with a live version.
        waiting: int - Live versions with no current verdict.
        published: int - Grades the agent published.
        manual: int - Versions waiting for the teacher.
        appealed: int - Open appeals.
        final: int - The teacher's final grades.
        late: int - Live versions sent after the deadline.

    """

    bdz: Bdz
    sent: int
    waiting: int
    published: int
    manual: int
    appealed: int
    final: int
    late: int


@dataclass(frozen=True, slots=True)
class RosterLine:
    """One student on a БДЗ roster.

    Attributes:
        student: Student - The roster row.
        submission: BdzSubmission | None - The live version, if they sent one.
        status: VerdictStatus | None - The current verdict, if there is one.

    """

    student: Student
    submission: BdzSubmission | None
    status: VerdictStatus | None


@dataclass(frozen=True, slots=True)
class _Pdfs:
    """The two stored PDFs of a new БДЗ.

    Attributes:
        statement: StoredFile - The statement on disk.
        statement_pages: int - Its pages.
        statement_tg_file_id: str - Telegram's id, to send it again.
        solutions: StoredFile | None - The solutions on disk, when given.
        solutions_pages: int | None - Their pages.
        solutions_tg_file_id: str | None - Telegram's id.

    """

    statement: StoredFile
    statement_pages: int
    statement_tg_file_id: str
    solutions: StoredFile | None
    solutions_pages: int | None
    solutions_tg_file_id: str | None


@final
class CreateBdz:
    """Publish a БДЗ: files, scheme, a ledger item and a notice."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        notifications: NotificationsApi,
        files: FileStore,
        audit: AuditLog,
        uow: UnitOfWork,
        clock: Clock,
        guard: AdminGuard,
        limits: BdzLimits,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._notifications: NotificationsApi = notifications
        self._files: FileStore = files
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock
        self._guard: AdminGuard = guard
        self._max_pages: int = limits.max_pages

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        draft: BdzDraft,
        statement: Upload,
        solutions: Upload | None,
    ) -> Bdz:
        """Publish it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            draft: BdzDraft - The title, the deadline and the scheme.
            statement: Upload - The statement PDF.
            solutions: Upload | None - The solutions PDF; without it the agent solves
                the tasks itself.

        Returns:
            Bdz - The published assignment.

        Raises:
            InvalidSchemeError: If the title or the scheme is empty.

        A work type of another group or one that accumulates is refused by
        `_record`; the stored files are deleted on any failure.

        """
        self._guard.require(actor)
        title = " ".join(draft.title.split())
        if not 1 <= len(title) <= _TITLE_LIMIT or not draft.tasks:
            raise InvalidSchemeError
        numbers = [task.number for task in draft.tasks]
        if numbers != list(range(1, len(numbers) + 1)):
            raise InvalidSchemeError
        now = self._clock.now()
        pdfs = await self._store(statement, solutions, now)
        try:
            return await self._record(actor, group_id, draft, title, pdfs, now)
        except BaseException:
            # A stored file without a row would be lost on disk.
            await self._files.delete(pdfs.statement.relative_path)
            if pdfs.solutions is not None:
                await self._files.delete(pdfs.solutions.relative_path)
            raise

    async def _store(
        self,
        statement: Upload,
        solutions: Upload | None,
        now: datetime,
    ) -> _Pdfs:
        """Store both PDFs; when the second is refused, the first goes too.

        Args:
            statement: Upload - The statement PDF.
            solutions: Upload | None - The solutions PDF, when given.
            now: datetime - Names the month folder.

        Returns:
            _Pdfs - Both files and their page counts.

        """
        first, first_pages = await store_pdf(
            self._files,
            statement.data,
            now,
            self._max_pages,
        )
        if solutions is None:
            return _Pdfs(first, first_pages, statement.tg_file_id, None, None, None)
        try:
            second, second_pages = await store_pdf(
                self._files,
                solutions.data,
                now,
                self._max_pages,
            )
        except BaseException:
            await self._files.delete(first.relative_path)
            raise
        return _Pdfs(
            first,
            first_pages,
            statement.tg_file_id,
            second,
            second_pages,
            solutions.tg_file_id,
        )

    async def _record(
        self,
        actor: int,
        group_id: uuid.UUID,
        draft: BdzDraft,
        title: str,
        pdfs: _Pdfs,
        now: datetime,
    ) -> Bdz:
        """Write the assignment, its ledger item and the notice.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            draft: BdzDraft - The deadline, the work type and the scheme.
            title: str - The cleaned title.
            pdfs: _Pdfs - The stored files.
            now: datetime - When.

        Returns:
            Bdz - The published assignment.

        Raises:
            WorkTypeNotFoundError: If the work type is not of this group.
            WorkTypeNotProportionalError: If the work type accumulates.

        """
        maximum = sum((task.max_points for task in draft.tasks), Decimal(0))
        async with self._uow:
            group = await _open(self._roster, group_id)
            work_type = await self._gradebook.work_type(draft.work_type_id)
            if work_type is None or work_type.group_id != group_id:
                raise WorkTypeNotFoundError
            if work_type.mode is not ScoringMode.PROPORTIONAL:
                raise WorkTypeNotProportionalError
            item = await self._gradebook.create_item(
                draft.work_type_id,
                title,
                maximum,
                draft.deadline,
            )
            bdz = Bdz(
                bdz_id=uuid.uuid4(),
                group_id=group_id,
                work_type_id=draft.work_type_id,
                item_id=item.item_id,
                title=title,
                deadline=draft.deadline,
                max_points=maximum,
                statement_path=pdfs.statement.relative_path,
                statement_tg_file_id=pdfs.statement_tg_file_id,
                statement_pages=pdfs.statement_pages,
                solutions_path=(
                    None if pdfs.solutions is None else pdfs.solutions.relative_path
                ),
                solutions_tg_file_id=pdfs.solutions_tg_file_id,
                solutions_pages=pdfs.solutions_pages,
                created_at=now,
            )
            await self._assignments.add(bdz, draft.tasks)
            _ = await self._notifications.notify_group(
                group_id,
                NotificationKind.BDZ_PUBLISHED,
                {
                    "title": title,
                    "deadline": draft.deadline.isoformat(),
                    "group": group.title,
                },
                f"bdz:{bdz.bdz_id}",
            )
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.ADMIN,
                    actor_id=str(actor),
                    action="bdz.created",
                    entity="bdz",
                    entity_id=str(bdz.bdz_id),
                ),
            )
            await self._uow.commit()
        return bdz


@final
class UpdateBdzDeadline:
    """Move a deadline, and the ledger item follows."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        audit: AuditLog,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, bdz_id: uuid.UUID, deadline: datetime) -> Bdz:
        """Move it.

        Args:
            actor: int - Teacher's Telegram id.
            bdz_id: uuid.UUID - The БДЗ.
            deadline: datetime - The new deadline.

        Returns:
            Bdz - The assignment.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.

        """
        self._guard.require(actor)
        async with self._uow:
            found = await self._assignments.get(bdz_id)
            if found is None or found.item_id is None:
                raise BdzNotFoundError
            _ = await _open(self._roster, found.group_id)
            changed = Bdz(
                found.bdz_id,
                found.group_id,
                found.work_type_id,
                found.item_id,
                found.title,
                deadline,
                found.max_points,
                found.statement_path,
                found.statement_tg_file_id,
                found.statement_pages,
                found.solutions_path,
                found.solutions_tg_file_id,
                found.solutions_pages,
                found.created_at,
            )
            _ = await self._gradebook.update_item(
                found.item_id,
                title=found.title,
                max_points=found.max_points,
                counts_from=deadline,
            )
            await self._assignments.save_deadline(changed)
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.ADMIN,
                    actor_id=str(actor),
                    action="bdz.deadline",
                    entity="bdz",
                    entity_id=str(bdz_id),
                    after={"deadline": deadline.isoformat()},
                ),
            )
            await self._uow.commit()
        return changed


@final
class MoveBdz:
    """Move a БДЗ, with its grades, to another proportional work type."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        audit: AuditLog,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        bdz_id: uuid.UUID,
        work_type_id: uuid.UUID,
    ) -> Bdz:
        """Move it.

        An accumulating work type, or one from another group, is refused.

        Args:
            actor: int - Teacher's Telegram id.
            bdz_id: uuid.UUID - The БДЗ.
            work_type_id: uuid.UUID - The work type, of the same group.

        Returns:
            Bdz - The assignment.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.

        """
        self._guard.require(actor)
        async with self._uow:
            found = await self._assignments.get(bdz_id)
            if found is None or found.item_id is None:
                raise BdzNotFoundError
            _ = await _open(self._roster, found.group_id)
            _ = await self._gradebook.move_item(found.item_id, work_type_id)
            changed = dataclasses.replace(found, work_type_id=work_type_id)
            await self._assignments.save_work_type(changed)
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.ADMIN,
                    actor_id=str(actor),
                    action="bdz.moved",
                    entity="bdz",
                    entity_id=str(bdz_id),
                    before={"work_type_id": str(found.work_type_id)},
                    after={"work_type_id": str(work_type_id)},
                ),
            )
            await self._uow.commit()
        return changed


@final
class DeleteBdz:
    """Delete a БДЗ, its files, its ledger item and its verdicts."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        reviews: ReviewApi,
        files: FileStore,
        audit: AuditLog,
        uow: UnitOfWork,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._reviews: ReviewApi = reviews
        self._files: FileStore = files
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, bdz_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            bdz_id: uuid.UUID - The БДЗ.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.

        """
        self._guard.require(actor)
        async with self._uow:
            found = await self._assignments.get(bdz_id)
            if found is None:
                raise BdzNotFoundError
            versions = await self._submissions.of_bdz(bdz_id)
            work_ids = [row.submission_id for row in versions]
            await self._reviews.forget_works("bdz", work_ids)
            if found.item_id is not None:
                await self._gradebook.delete_item(found.item_id)
            _ = await self._assignments.delete(bdz_id)
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.ADMIN,
                    actor_id=str(actor),
                    action="bdz.deleted",
                    entity="bdz",
                    entity_id=str(bdz_id),
                ),
            )
            await self._uow.commit()
        for path in _paths(found, versions):
            await self._files.delete(path)


@final
class ListBdz:
    """A group's БДЗ with how far the checking has got."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        reviews: ReviewApi,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._reviews: ReviewApi = reviews
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> list[BdzSummary]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            list[BdzSummary] - Newest first.

        """
        self._guard.require(actor)
        found = await self._assignments.of_group(group_id)
        summaries: list[BdzSummary] = []
        for bdz in found:
            versions = await self._submissions.of_bdz(bdz.bdz_id)
            summaries.append(await _summary(self._reviews, bdz, versions))
        return summaries


@final
class BdzRoster:
    """Every student of the group, with the live version and its verdict."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        reviews: ReviewApi,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._reviews: ReviewApi = reviews
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, bdz_id: uuid.UUID) -> list[RosterLine]:
        """Read it.

        Args:
            actor: int - Teacher's Telegram id.
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            list[RosterLine] - One row per student.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.

        """
        self._guard.require(actor)
        found = await self._assignments.get(bdz_id)
        if found is None:
            raise BdzNotFoundError
        live = {
            row.student_id: row
            for row in await self._submissions.of_bdz(bdz_id)
            if row.status is SubmissionStatus.LIVE
        }
        lines: list[RosterLine] = []
        for student in await self._roster.students_of(found.group_id):
            submission = live.get(student.student_id)
            status = await _status(self._reviews, submission)
            lines.append(RosterLine(student, submission, status))
        return lines


async def _summary(
    reviews: ReviewApi,
    bdz: Bdz,
    versions: Sequence[BdzSubmission],
) -> BdzSummary:
    sent = waiting = published = manual = appealed = final = late = 0
    for row in versions:
        if row.status is not SubmissionStatus.LIVE:
            continue
        sent += 1
        if row.is_late:
            late += 1
        status = await _status(reviews, row)
        if status is None:
            waiting += 1
        elif status is VerdictStatus.PUBLISHED:
            published += 1
        elif status is VerdictStatus.MANUAL:
            manual += 1
        elif status is VerdictStatus.APPEALED:
            appealed += 1
        elif status is VerdictStatus.FINAL:
            final += 1
    return BdzSummary(bdz, sent, waiting, published, manual, appealed, final, late)


async def _status(
    reviews: ReviewApi,
    submission: BdzSubmission | None,
) -> VerdictStatus | None:
    if submission is None:
        return None
    verdict = await reviews.current("bdz", submission.submission_id)
    return None if verdict is None else verdict.status


async def _open(roster: RosterApi, group_id: uuid.UUID) -> Group:
    group = await roster.group(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group


def _paths(bdz: Bdz, versions: Sequence[BdzSubmission]) -> list[str]:
    paths = [bdz.statement_path]
    if bdz.solutions_path is not None:
        paths.append(bdz.solutions_path)
    paths.extend(row.path for row in versions)
    return paths
