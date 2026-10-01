"""Deadline reminders: who is due one now, queued once per student and assignment."""

from __future__ import annotations

from datetime import timedelta
from typing import final

from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.homework.application.ports import (
    AssignmentRepository,
    SubmissionRepository,
)
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import BindingStatus

_LONGEST_LEAD = timedelta(days=7)


@final
class QueueReminders:
    """Students without a live version, inside their group's reminder window."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        notifications: NotificationsApi,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._notifications: NotificationsApi = notifications
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock

    async def __call__(self) -> int:
        """Queue them; a reminder already queued is not queued again.

        Returns:
            int - How many students were queued now.

        """
        now = self._clock.now()
        queued = 0
        async with self._uow:
            for assignment in await self._assignments.due_between(
                now,
                now + _LONGEST_LEAD,
            ):
                group = await self._roster.group(assignment.group_id)
                lead = (
                    None
                    if group is None
                    else timedelta(hours=group.settings.reminder_hours)
                )
                if group is None or not group.is_active or lead is None:
                    continue
                if assignment.deadline - lead > now:
                    continue
                live = {
                    s.student_id
                    for s in await self._submissions.live_of_assignment(
                        assignment.assignment_id,
                    )
                }
                waiting = [
                    s.student_id
                    for s in await self._roster.students_of(assignment.group_id)
                    if s.binding is BindingStatus.BOUND and s.student_id not in live
                ]
                muted = await self._notifications.muted(waiting)
                for student_id in waiting:
                    if student_id in muted:
                        continue
                    queued += await self._notifications.notify_student(
                        student_id,
                        NotificationKind.DEADLINE_REMINDER,
                        {
                            "title": assignment.title,
                            "deadline": assignment.deadline.isoformat(),
                        },
                        dedupe_key=f"reminder:{assignment.assignment_id}",
                    )
            await self._uow.commit()
        return queued
