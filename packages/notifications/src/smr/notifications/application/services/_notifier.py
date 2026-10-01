"""Queue notices in the caller's transaction."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping
from typing import final

from smr.core.access import AdminGuard
from smr.notifications.application.ports import Outbox, Preferences
from smr.notifications.domain import NotificationKind
from smr.roster.application.contracts import RosterApi
from smr.roster.domain import BindingStatus


def _key(dedupe_key: str | None, tg_user_id: int) -> str | None:
    return None if dedupe_key is None else f"{dedupe_key}:{tg_user_id}"


@final
class Notifier:
    """`NotificationsApi`; it never commits."""

    def __init__(
        self,
        outbox: Outbox,
        preferences: Preferences,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._outbox: Outbox = outbox
        self._preferences: Preferences = preferences
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def notify_group(
        self,
        group_id: uuid.UUID,
        kind: NotificationKind,
        payload: Mapping[str, object],
        dedupe_key: str | None = None,
    ) -> int:
        """Tell every bound student of a group.

        Args:
            group_id: uuid.UUID - The group.
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of the text.
            dedupe_key: str | None - What makes a repeat a repeat.

        Returns:
            int - How many students were queued.

        """
        queued = 0
        for student in await self._roster.students_of(group_id):
            if (
                student.binding is BindingStatus.BOUND
                and student.tg_user_id is not None
            ):
                queued += await self._outbox.add(
                    student.tg_user_id,
                    kind,
                    payload,
                    _key(dedupe_key, student.tg_user_id),
                )
        return queued

    async def notify_student(
        self,
        student_id: uuid.UUID,
        kind: NotificationKind,
        payload: Mapping[str, object],
        dedupe_key: str | None = None,
    ) -> bool:
        """Tell one student, if their account is bound.

        Args:
            student_id: uuid.UUID - The student.
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of the text.
            dedupe_key: str | None - What makes a repeat a repeat.

        Returns:
            bool - False when the student has no bound account or it is a repeat.

        """
        student = await self._roster.student(student_id)
        if (
            student is None
            or student.binding is not BindingStatus.BOUND
            or student.tg_user_id is None
        ):
            return False
        return await self._outbox.add(
            student.tg_user_id,
            kind,
            payload,
            _key(dedupe_key, student.tg_user_id),
        )

    async def notify_account(
        self,
        tg_user_id: int,
        kind: NotificationKind,
        payload: Mapping[str, object],
    ) -> None:
        """Tell one Telegram account.

        Args:
            tg_user_id: int - The account.
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of the text.

        """
        _ = await self._outbox.add(tg_user_id, kind, payload, None)

    async def notify_admins(
        self,
        kind: NotificationKind,
        payload: Mapping[str, object],
    ) -> None:
        """Tell every teacher.

        Args:
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of the text.

        """
        for admin in sorted(self._guard.admin_ids):
            _ = await self._outbox.add(admin, kind, payload, None)

    async def muted(self, student_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Tell which students turned reminders off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.

        Returns:
            set[uuid.UUID] - Those with reminders off.

        """
        return await self._preferences.muted(student_ids)
