"""A file the agent cannot open is handed to the teacher at once."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import final

from smr.core.clock import Clock
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.review.application.ports import VerdictRepository
from smr.review.domain import GraderKind, TaskVerdict, Verdict, VerdictStatus


@final
class FlagUnreadable:
    """Record a manual verdict so the agent never receives the file.

    The caller owns the transaction: this writes the verdict and the notice
    and does not commit.
    """

    def __init__(
        self,
        verdicts: VerdictRepository,
        notifications: NotificationsApi,
        clock: Clock,
    ) -> None:
        self._verdicts: VerdictRepository = verdicts
        self._notifications: NotificationsApi = notifications
        self._clock: Clock = clock

    async def __call__(
        self,
        source: str,
        work_id: uuid.UUID,
        sha256: str,
        task_ref: uuid.UUID,
        student_ref: uuid.UUID,
        title: str,
        max_points: Decimal,
        explanation: str,
    ) -> None:
        """Flag the version.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.
            sha256: str - The file the flag is about.
            task_ref: uuid.UUID - The assignment.
            student_ref: uuid.UUID - The roster row.
            title: str - The assignment's title.
            max_points: Decimal - The one task's maximum.
            explanation: str - Why the file cannot be read, in Russian.

        """
        now = self._clock.now()
        verdict_id = uuid.uuid4()
        task = TaskVerdict(
            number=1,
            points=Decimal(0),
            max_points=max_points,
            explanation=explanation,
            unreadable=True,
            unsure=False,
            manipulation=False,
            pages=(1,),
        )
        await self._verdicts.add(
            Verdict(
                verdict_id=verdict_id,
                source=source,
                work_id=work_id,
                work_sha256=sha256,
                task_ref=task_ref,
                student_ref=student_ref,
                grader_kind=GraderKind.AGENT,
                grader="system",
                status=VerdictStatus.MANUAL,
                total=Decimal(0),
                max_points=max_points,
                summary=explanation,
                pages_seen=1,
                created_at=now,
                published_at=None,
                tasks=(task,),
            ),
        )
        _ = await self._notifications.notify_student(
            student_ref,
            NotificationKind.REVIEW_MANUAL,
            {"title": title, "pages": [1], "label": "домашнее задание"},
            f"review:{verdict_id}",
        )
