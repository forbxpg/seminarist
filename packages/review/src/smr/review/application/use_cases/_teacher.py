"""The teacher's queue and the final grade."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from operator import attrgetter
from typing import final

from smr.core.access import AdminGuard
from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.review.application.ports import (
    AppealRepository,
    ReviewSource,
    TaskSheet,
    VerdictRepository,
)
from smr.review.domain import (
    Appeal,
    AppealStatus,
    GraderKind,
    SchemeTask,
    StaleWorkError,
    TaskVerdict,
    Verdict,
    VerdictNotFoundError,
    VerdictRejectedError,
    VerdictStatus,
)

from ._keys import source_of

_ZERO = Decimal(0)
_CENT = Decimal("0.01")
_SUMMARY_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class QueueItem:
    """One verdict waiting for the teacher.

    Attributes:
        verdict: Verdict - The agent's verdict.
        appeal: Appeal | None - The open appeal, when the student filed one.
        title: str - The assignment.
        version: int - The version.
        is_late: bool - Sent after the deadline.

    """

    verdict: Verdict
    appeal: Appeal | None
    title: str
    version: int
    is_late: bool


@dataclass(frozen=True, slots=True)
class TeacherView:
    """Everything the teacher needs to grade one verdict.

    Attributes:
        verdict: Verdict - The agent's verdict.
        appeal: Appeal | None - The appeal, if any.
        work_path: str - The student's PDF.
        sheet: TaskSheet - The statement, the solutions and the scheme.

    """

    verdict: Verdict
    appeal: Appeal | None
    work_path: str
    sheet: TaskSheet


@final
class TeacherQueue:
    """Manual verdicts and open appeals, oldest first."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        appeals: AppealRepository,
        guard: AdminGuard,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int) -> list[QueueItem]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.

        Returns:
            list[QueueItem] - The queue. A verdict whose work is gone is omitted.

        """
        self._guard.require(actor)
        manuals = await self._verdicts.of_status((VerdictStatus.MANUAL,))
        appealed = await self._verdicts.of_status((VerdictStatus.APPEALED,))
        rows = sorted((*manuals, *appealed), key=attrgetter("created_at"))
        items: list[QueueItem] = []
        for verdict in rows:
            item = await self._item(verdict)
            if item is not None:
                items.append(item)
        return items

    async def _item(self, verdict: Verdict) -> QueueItem | None:
        source = source_of(self._sources, verdict.source)
        work = await source.work(verdict.work_id)
        if work is None:
            return None
        appeal = await self._appeals.of_verdict(verdict.verdict_id)
        if verdict.status is VerdictStatus.APPEALED and not _open(appeal):
            return None
        return QueueItem(verdict, appeal, work.title, work.version, work.is_late)


@final
class OpenForTeacher:
    """One queued verdict, with the files the teacher reads."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        appeals: AppealRepository,
        guard: AdminGuard,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, verdict_id: uuid.UUID) -> TeacherView:
        """Open it.

        Args:
            actor: int - Teacher's Telegram id.
            verdict_id: uuid.UUID - The agent's verdict.

        Returns:
            TeacherView - The verdict, the appeal and the files.

        Raises:
            VerdictNotFoundError: If there is no such verdict.
            StaleWorkError: If its version is no longer live.

        """
        self._guard.require(actor)
        verdict = await self._verdicts.get(verdict_id)
        if verdict is None:
            raise VerdictNotFoundError
        source = source_of(self._sources, verdict.source)
        work = await source.work(verdict.work_id)
        if work is None:
            raise StaleWorkError
        return TeacherView(
            verdict,
            await self._appeals.of_verdict(verdict_id),
            await source.work_path(verdict.work_id),
            await source.sheet(verdict.task_ref),
        )


@final
class FinalizeByTeacher:
    """Replace an agent's verdict with the teacher's final grade."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        appeals: AppealRepository,
        notifications: NotificationsApi,
        audit: AuditLog,
        uow: UnitOfWork,
        clock: Clock,
        guard: AdminGuard,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals
        self._notifications: NotificationsApi = notifications
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        verdict_id: uuid.UUID,
        scores: Mapping[int, Decimal],
        explanations: Mapping[int, str],
        summary: str,
    ) -> Verdict:
        """Record it.

        Args:
            actor: int - Teacher's Telegram id.
            verdict_id: uuid.UUID - The agent's verdict.
            scores: Mapping[int, Decimal] - Points per task number.
            explanations: Mapping[int, str] - A comment per task; the agent's
                text stays where the teacher wrote none.
            summary: str - A short overview; it may be empty.

        Returns:
            Verdict - The teacher's verdict.

        Raises:
            VerdictNotFoundError: If there is no such verdict.
            VerdictRejectedError: If it is not waiting, or the scores miss the scheme.
            StaleWorkError: If the version is no longer live.

        """
        self._guard.require(actor)
        if len(summary) > _SUMMARY_LIMIT:
            msg = "summary is too long"
            raise VerdictRejectedError(msg)
        async with self._uow:
            old = await self._verdicts.get(verdict_id)
            if old is None:
                raise VerdictNotFoundError
            if old.status not in {VerdictStatus.MANUAL, VerdictStatus.APPEALED}:
                msg = "verdict is not awaiting the teacher"
                raise VerdictRejectedError(msg)
            source = source_of(self._sources, old.source)
            work = await source.work(old.work_id, lock=True)
            if work is None:
                raise StaleWorkError
            sheet = await source.sheet(old.task_ref)
            _check_scores(scores, sheet.scheme)
            previous = {task.number: task.explanation for task in old.tasks}
            tasks = tuple(
                TaskVerdict(
                    number=item.number,
                    points=scores[item.number],
                    max_points=item.max_points,
                    explanation=explanations.get(
                        item.number,
                        previous.get(item.number, ""),
                    ),
                    unreadable=False,
                    unsure=False,
                    manipulation=False,
                    pages=(),
                )
                for item in sheet.scheme
            )
            total = sum((task.points for task in tasks), _ZERO)
            now = self._clock.now()
            final = Verdict(
                verdict_id=uuid.uuid4(),
                source=old.source,
                work_id=old.work_id,
                work_sha256=old.work_sha256,
                task_ref=old.task_ref,
                student_ref=old.student_ref,
                grader_kind=GraderKind.TEACHER,
                grader=str(actor),
                status=VerdictStatus.FINAL,
                total=total,
                max_points=sheet.max_points,
                summary=summary,
                pages_seen=old.pages_seen,
                created_at=now,
                published_at=now,
                tasks=tasks,
            )
            await self._verdicts.set_status(old.verdict_id, VerdictStatus.SUPERSEDED)
            await self._uow.flush()
            await self._verdicts.add(final)
            appeal = await self._appeals.of_verdict(old.verdict_id)
            if appeal is not None and appeal.status is AppealStatus.OPEN:
                await self._appeals.resolve(appeal.appeal_id, final.verdict_id, now)
            await source.apply_grade(old.work_id, total, teacher=actor, agent=None)
            _ = await self._notifications.notify_student(
                old.student_ref,
                NotificationKind.REVIEW_FINAL,
                {
                    "title": work.title,
                    "total": _money(total),
                    "max": _money(sheet.max_points),
                    "before": _money(old.total),
                },
                f"review:{final.verdict_id}",
            )
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.ADMIN,
                    actor_id=str(actor),
                    action="review.finalized",
                    entity="verdict",
                    entity_id=str(final.verdict_id),
                    before={"total": _money(old.total)},
                    after={"total": _money(total)},
                ),
            )
            await self._uow.commit()
        return final


def _open(appeal: Appeal | None) -> bool:
    return appeal is not None and appeal.status is AppealStatus.OPEN


def _money(value: Decimal) -> str:
    text = format(value.quantize(_CENT), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _check_scores(scores: Mapping[int, Decimal], scheme: Sequence[SchemeTask]) -> None:
    expected = [item.number for item in scheme]
    missing = [number for number in expected if number not in scores]
    if missing:
        msg = f"missing tasks: {missing}"
        raise VerdictRejectedError(msg)
    extra = [number for number in scores if number not in expected]
    if extra:
        msg = f"extra tasks: {extra}"
        raise VerdictRejectedError(msg)
    limits = {item.number: item.max_points for item in scheme}
    for number, points in scores.items():
        limit = limits[number]
        if points < _ZERO:
            msg = f"task {number}: points {points} below 0"
            raise VerdictRejectedError(msg)
        if points > limit:
            msg = f"task {number}: points {points} above max {limit}"
            raise VerdictRejectedError(msg)
        if points != points.quantize(_CENT):
            msg = f"task {number}: more than 2 decimals"
            raise VerdictRejectedError(msg)
