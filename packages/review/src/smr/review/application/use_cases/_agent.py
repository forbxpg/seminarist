"""The agent's side: the queue, the files and a verdict."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from operator import itemgetter
from typing import final

from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.review.application.ports import ReviewSource, TaskSheet, VerdictRepository
from smr.review.domain import (
    AlreadyReviewedError,
    GraderKind,
    StaleWorkError,
    TaskVerdict,
    Verdict,
    VerdictRejectedError,
    VerdictStatus,
    appeal_open_until,
    check_pages_seen,
    check_tasks,
    status_for,
)

from ._keys import parse_key, source_of

_ZERO = Decimal(0)
_CENT = Decimal("0.01")
_SUMMARY_LIMIT = 1000
_GRADER_LIMIT = 64


@dataclass(frozen=True, slots=True)
class PendingWork:
    """A live version with no current verdict.

    Attributes:
        work_ref: str - `source:work_id`.
        task_key: str - `source:task_ref`.
        title: str - The assignment.
        version: int - The version.
        pages: int - How many pages.
        sha256: str - The file.
        is_late: bool - Sent after the deadline.

    """

    work_ref: str
    task_key: str
    title: str
    version: int
    pages: int
    sha256: str
    is_late: bool


@dataclass(frozen=True, slots=True)
class TaskInput:
    """One task as the agent sent it.

    Attributes:
        number: int - The task.
        points: Decimal - The score.
        explanation: str - Written to the student.
        unreadable: bool - A page could not be read.
        unsure: bool - The agent is not confident.
        manipulation: bool - The work addresses the grader.
        pages: tuple[int, ...] - Pages the task was found on.

    """

    number: int
    points: Decimal
    explanation: str
    unreadable: bool
    unsure: bool
    manipulation: bool
    pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class VerdictInput:
    """A verdict as the agent sent it.

    Attributes:
        work_ref: str - `source:work_id`.
        sha256: str - The file it graded.
        grader: str - The model's name.
        summary: str - A short overview.
        pages_seen: tuple[int, ...] - Every page it read.
        tasks: tuple[TaskInput, ...] - One row per task.

    """

    work_ref: str
    sha256: str
    grader: str
    summary: str
    pages_seen: tuple[int, ...]
    tasks: tuple[TaskInput, ...]


@dataclass(frozen=True, slots=True)
class VerdictOutcome:
    """What submitting a verdict did.

    Attributes:
        status: str - `published` or `manual`.
        total: Decimal - The sum.
        max_points: Decimal - The scheme's sum.

    """

    status: str
    total: Decimal
    max_points: Decimal


@final
class PendingWorks:
    """Live works no current verdict covers yet."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts

    async def __call__(self) -> list[PendingWork]:
        """List them, oldest first.

        Returns:
            list[PendingWork] - The works. No student id, no name.

        """
        found: list[tuple[datetime, PendingWork]] = []
        for source in self._sources:
            reviewed = await self._verdicts.current_work_ids(source.name)
            for work in await source.live_works():
                if work.work_id in reviewed:
                    continue
                found.append(
                    (
                        work.sent_at,
                        PendingWork(
                            work_ref=f"{source.name}:{work.work_id}",
                            task_key=f"{source.name}:{work.task_ref}",
                            title=work.title,
                            version=work.version,
                            pages=work.pages,
                            sha256=work.sha256,
                            is_late=work.is_late,
                        ),
                    ),
                )
        found.sort(key=itemgetter(0))
        return [work for _, work in found]


@final
class TaskSheetFor:
    """The scheme of an assignment."""

    def __init__(self, sources: Sequence[ReviewSource]) -> None:
        self._sources: Sequence[ReviewSource] = sources

    async def __call__(self, task_key: str) -> TaskSheet:
        """Read it.

        Args:
            task_key: str - `source:task_ref`.

        Returns:
            TaskSheet - The scheme and the file paths.

        """
        name, task_ref = parse_key(task_key)
        return await source_of(self._sources, name).sheet(task_ref)


@final
class WorkFile:
    """Where a live version's PDF is, and how many pages it has."""

    def __init__(self, sources: Sequence[ReviewSource]) -> None:
        self._sources: Sequence[ReviewSource] = sources

    async def __call__(self, work_ref: str) -> tuple[str, int]:
        """Read it.

        Args:
            work_ref: str - `source:work_id`.

        Returns:
            tuple[str, int] - The FileStore path and the page count.

        Raises:
            StaleWorkError: If the version is not live.

        """
        name, work_id = parse_key(work_ref)
        source = source_of(self._sources, name)
        work = await source.work(work_id)
        if work is None:
            raise StaleWorkError
        return await source.work_path(work_id), work.pages


@final
class SubmitVerdict:
    """Record an agent's verdict and tell the student, or the teacher."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        notifications: NotificationsApi,
        audit: AuditLog,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._notifications: NotificationsApi = notifications
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock

    async def __call__(self, data: VerdictInput) -> VerdictOutcome:
        """Check it and store it.

        Args:
            data: VerdictInput - What the agent sent.

        Returns:
            VerdictOutcome - The status and the totals.

        Raises:
            StaleWorkError: If the version is gone or the file changed.
            AlreadyReviewedError: If it already has a current verdict.

        """
        _limits(data.grader, data.summary)
        name, work_id = parse_key(data.work_ref)
        source = source_of(self._sources, name)
        async with self._uow:
            work = await source.work(work_id, lock=True)
            if work is None or work.sha256 != data.sha256:
                raise StaleWorkError
            if await self._verdicts.current(name, work_id) is not None:
                raise AlreadyReviewedError
            sheet = await source.sheet(work.task_ref)
            tasks = tuple(_task(row) for row in data.tasks)
            check_tasks(tasks, sheet.scheme, work.pages)
            check_pages_seen(data.pages_seen, work.pages)
            limits = {item.number: item.max_points for item in sheet.scheme}
            tasks = tuple(
                dataclasses.replace(task, max_points=limits[task.number])
                for task in tasks
            )
            status = status_for(tasks)
            total = sum((task.points for task in tasks), _ZERO)
            now = self._clock.now()
            verdict = Verdict(
                verdict_id=uuid.uuid4(),
                source=name,
                work_id=work_id,
                work_sha256=data.sha256,
                task_ref=work.task_ref,
                student_ref=work.student_ref,
                grader_kind=GraderKind.AGENT,
                grader=data.grader,
                status=status,
                total=total,
                max_points=sheet.max_points,
                summary=data.summary,
                pages_seen=work.pages,
                created_at=now,
                published_at=now if status is VerdictStatus.PUBLISHED else None,
                tasks=tasks,
            )
            await self._verdicts.add(verdict)
            await self._tell(source, work.title, work.student_ref, verdict, tasks, now)
            await self._audit.record(_agent_audit(verdict, data.work_ref))
            for task in tasks:
                if task.manipulation:
                    await self._audit.record(
                        _manipulation(data.grader, data.work_ref, task),
                    )
            await self._uow.commit()
        return VerdictOutcome(status.value, total, sheet.max_points)

    async def _tell(
        self,
        source: ReviewSource,
        title: str,
        student_id: uuid.UUID,
        verdict: Verdict,
        tasks: tuple[TaskVerdict, ...],
        now: datetime,
    ) -> None:
        dedupe = f"review:{verdict.verdict_id}"
        if verdict.status is VerdictStatus.MANUAL:
            pages = sorted(
                {page for task in tasks if task.unreadable for page in task.pages},
            )
            _ = await self._notifications.notify_student(
                student_id,
                NotificationKind.REVIEW_MANUAL,
                {"title": title, "pages": pages},
                dedupe,
            )
            return
        await source.apply_grade(
            verdict.work_id,
            verdict.total,
            teacher=None,
            agent=verdict.grader,
        )
        until = appeal_open_until(now).isoformat()
        _ = await self._notifications.notify_student(
            student_id,
            NotificationKind.REVIEW_PUBLISHED,
            {
                "title": title,
                "total": _money(verdict.total),
                "max": _money(verdict.max_points),
                "appeal_until": until,
            },
            dedupe,
        )


def _task(row: TaskInput) -> TaskVerdict:
    return TaskVerdict(
        number=row.number,
        points=row.points,
        max_points=_ZERO,
        explanation=row.explanation,
        unreadable=row.unreadable,
        unsure=row.unsure,
        manipulation=row.manipulation,
        pages=row.pages,
    )


def _limits(grader: str, summary: str) -> None:
    if not 1 <= len(grader) <= _GRADER_LIMIT:
        msg = "grader is 1..64 characters"
        raise VerdictRejectedError(msg)
    if len(summary) > _SUMMARY_LIMIT:
        msg = "summary is too long"
        raise VerdictRejectedError(msg)


def _money(value: Decimal) -> str:
    text = format(value.quantize(_CENT), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _agent_audit(verdict: Verdict, work_ref: str) -> AuditEntry:
    action = (
        "review.manual"
        if verdict.status is VerdictStatus.MANUAL
        else "review.published"
    )
    return AuditEntry(
        actor_kind=ActorKind.AGENT,
        actor_id=verdict.grader,
        action=action,
        entity="verdict",
        entity_id=str(verdict.verdict_id),
        after={"work_ref": work_ref, "total": _money(verdict.total)},
    )


def _manipulation(grader: str, work_ref: str, task: TaskVerdict) -> AuditEntry:
    return AuditEntry(
        actor_kind=ActorKind.AGENT,
        actor_id=grader,
        action="review.manipulation",
        entity="verdict",
        entity_id=work_ref,
        after={"work_ref": work_ref, "task": task.number, "pages": list(task.pages)},
    )
