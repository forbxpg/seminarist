"""Notices queued by other packages in their own transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Collection, Mapping

    from smr.notifications.domain import NotificationKind


class NotificationsApi(Protocol):
    """Queue notices to students and teachers."""

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
        ...

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
        ...

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
        ...

    async def notify_admins(
        self,
        kind: NotificationKind,
        payload: Mapping[str, object],
        dedupe_key: str | None = None,
    ) -> None:
        """Tell every teacher.

        Args:
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of the text.
            dedupe_key: str | None - What makes a repeat a repeat, per teacher.

        """
        ...

    async def muted(self, student_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Tell which students turned reminders off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.

        Returns:
            set[uuid.UUID] - Those with reminders off.

        """
        ...
