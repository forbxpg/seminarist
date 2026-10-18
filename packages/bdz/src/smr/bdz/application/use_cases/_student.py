"""A student reads the statement and sends one PDF."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import final

from smr.bdz.domain import (
    Bdz,
    BdzError,
    BdzNotFoundError,
    BdzSubmission,
    ConsentRequiredError,
    NotYourBdzError,
    SubmissionStatus,
)
from smr.bdz.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemySubmissions,
)
from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.core.files import FileStore, StoredFile
from smr.review.application.contracts import ReviewApi
from smr.review.domain import AppealOpenError, VerdictStatus, appeal_open_until
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import GroupArchivedError, GroupNotFoundError

from ._limits import BdzLimits
from ._pdf import store_pdf
from ._upload import Upload


@final
class SendBdz:
    """Accept one PDF. A new version voids the current verdict."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        submissions: SqlAlchemySubmissions,
        roster: RosterApi,
        reviews: ReviewApi,
        files: FileStore,
        audit: AuditLog,
        uow: UnitOfWork,
        clock: Clock,
        limits: BdzLimits,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._submissions: SqlAlchemySubmissions = submissions
        self._roster: RosterApi = roster
        self._reviews: ReviewApi = reviews
        self._files: FileStore = files
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock
        self._max_pages: int = limits.max_pages

    async def __call__(
        self,
        tg_user_id: int,
        bdz_id: uuid.UUID,
        upload: Upload,
    ) -> BdzSubmission:
        """Accept it.

        Args:
            tg_user_id: int - The account.
            bdz_id: uuid.UUID - The БДЗ.
            upload: Upload - The PDF.

        Returns:
            BdzSubmission - The live version.

        Raises:
            BdzError: If the БДЗ refuses the upload.
            AppealOpenError: If an appeal is open on the live version.
            GroupNotFoundError: If the group is gone.
            GroupArchivedError: If the group is archived.

        """
        saved, pages = await store_pdf(
            self._files,
            upload.data,
            self._clock.now(),
            self._max_pages,
        )
        try:
            submission, previous = await self._record(
                tg_user_id,
                bdz_id,
                upload,
                saved,
                pages,
            )
        except (BdzError, AppealOpenError, GroupNotFoundError, GroupArchivedError):
            await self._files.delete(saved.relative_path)
            raise
        if previous is not None:
            await self._files.delete(previous.path)
        return submission

    async def _record(
        self,
        tg_user_id: int,
        bdz_id: uuid.UUID,
        upload: Upload,
        saved: StoredFile,
        pages: int,
    ) -> tuple[BdzSubmission, BdzSubmission | None]:
        """Store the live version, voiding the previous one.

        Args:
            tg_user_id: int - The account.
            bdz_id: uuid.UUID - The БДЗ.
            upload: Upload - The PDF.
            saved: StoredFile - The file already on disk.
            pages: int - How many pages it has.

        Returns:
            tuple[BdzSubmission, BdzSubmission | None] - The new version and the old.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.
            NotYourBdzError: If the account is not an approved student of the group.
            ConsentRequiredError: If the current notice is not accepted.
            AppealOpenError: If an appeal is open on the live version.

        """
        async with self._uow:
            bdz = await self._assignments.get(bdz_id)
            if bdz is None:
                raise BdzNotFoundError
            _ = await _open(self._roster, bdz.group_id)
            student = await self._roster.bound_student(tg_user_id, bdz.group_id)
            if student is None:
                raise NotYourBdzError
            if not await self._roster.consented(student.student_id):
                raise ConsentRequiredError
            previous = await self._submissions.live(
                bdz_id,
                student.student_id,
                lock=True,
            )
            if previous is not None and await self._reviews.has_open_appeal(
                "bdz",
                previous.submission_id,
            ):
                raise AppealOpenError
            if previous is not None:
                await self._reviews.void("bdz", previous.submission_id)
                await self._submissions.supersede(previous.submission_id)
            version = await self._submissions.next_version(
                bdz_id,
                student.student_id,
            )
            submission = BdzSubmission(
                submission_id=uuid.uuid4(),
                bdz_id=bdz_id,
                student_id=student.student_id,
                version=version,
                status=SubmissionStatus.LIVE,
                path=saved.relative_path,
                tg_file_id=upload.tg_file_id,
                tg_file_unique_id=upload.tg_file_unique_id,
                size=saved.size,
                sha256=saved.sha256,
                pages=pages,
                sent_at=upload.sent_at,
                is_late=upload.sent_at > bdz.deadline,
            )
            await self._submissions.add(submission)
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.STUDENT,
                    actor_id=str(student.student_id),
                    action="bdz.sent",
                    entity="bdz_submission",
                    entity_id=str(submission.submission_id),
                    after={"version": version, "late": submission.is_late},
                ),
            )
            await self._uow.commit()
        return submission, previous


@final
class BdzStatement:
    """The statement PDF, never the solutions."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        roster: RosterApi,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._roster: RosterApi = roster

    async def __call__(self, tg_user_id: int, bdz_id: uuid.UUID) -> tuple[str, str]:
        """Read it.

        Args:
            tg_user_id: int - The account.
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            tuple[str, str] - Telegram's file id and the title.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.
            NotYourBdzError: If the account is not an approved student.

        """
        bdz = await self._assignments.get(bdz_id)
        if bdz is None:
            raise BdzNotFoundError
        student = await self._roster.bound_student(tg_user_id, bdz.group_id)
        if student is None:
            raise NotYourBdzError
        return bdz.statement_tg_file_id, bdz.title


@dataclass(frozen=True, slots=True)
class StudentBdz:
    """One БДЗ as a student sees it.

    Attributes:
        bdz: Bdz - The assignment.
        submission: BdzSubmission | None - The live version.
        status: VerdictStatus | None - The current verdict.
        total: Decimal | None - Its points.
        published_at: datetime | None - When the student was told.
        can_appeal: bool - Whether an appeal can still be filed.

    """

    bdz: Bdz
    submission: BdzSubmission | None
    status: VerdictStatus | None
    total: Decimal | None
    published_at: datetime | None
    can_appeal: bool


@final
class StudentBdzList:
    """The БДЗ of one group for one student."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        submissions: SqlAlchemySubmissions,
        roster: RosterApi,
        reviews: ReviewApi,
        clock: Clock,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._submissions: SqlAlchemySubmissions = submissions
        self._roster: RosterApi = roster
        self._reviews: ReviewApi = reviews
        self._clock: Clock = clock

    async def __call__(
        self,
        tg_user_id: int,
        group_id: uuid.UUID,
    ) -> list[StudentBdz]:
        """List them.

        Args:
            tg_user_id: int - The account.
            group_id: uuid.UUID - The group.

        Returns:
            list[StudentBdz] - Each assignment, the live version and the verdict.

        """
        found = await self._assignments.of_group(group_id)
        student = await self._roster.bound_student(tg_user_id, group_id)
        rows: list[StudentBdz] = []
        for bdz in found:
            live = None
            if student is not None:
                live = await self._submissions.live(bdz.bdz_id, student.student_id)
            rows.append(await _view(self._reviews, self._clock, bdz, live))
        return rows


async def _view(
    reviews: ReviewApi,
    clock: Clock,
    bdz: Bdz,
    submission: BdzSubmission | None,
) -> StudentBdz:
    status = None
    total = None
    published_at = None
    can_appeal = False
    if submission is not None:
        verdict = await reviews.current("bdz", submission.submission_id)
        if verdict is not None:
            status = verdict.status
            total = verdict.total
            published_at = verdict.published_at
            until = None if published_at is None else appeal_open_until(published_at)
            can_appeal = (
                status is VerdictStatus.PUBLISHED
                and until is not None
                and clock.now() <= until
            )
    return StudentBdz(bdz, submission, status, total, published_at, can_appeal)


async def _open(roster: RosterApi, group_id: uuid.UUID) -> None:
    group = await roster.group(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
