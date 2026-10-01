"""Ports of notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Collection, Mapping, Sequence
    from datetime import datetime

    from smr.notifications.domain import Notice, NotificationKind


class DeliveryError(Exception):
    """A notice could not be delivered."""


class DeliveryRetryError(DeliveryError):
    """Try again later.

    Attributes:
        after_seconds: float - How long Telegram asked to wait.

    """

    def __init__(self, after_seconds: float) -> None:
        super().__init__(f"retry after {after_seconds} s")
        self.after_seconds: float = after_seconds


class DeliveryGaveUpError(DeliveryError):
    """The account cannot be reached: it blocked the bot or does not exist."""


class Sender(Protocol):
    """Sends a text to a Telegram account."""

    async def send(self, tg_user_id: int, text: str) -> None:
        """Send it.

        Args:
            tg_user_id: int - The account.
            text: str - Telegram HTML.

        """
        ...


class Outbox(Protocol):
    """The notices waiting to be sent."""

    async def add(
        self,
        tg_user_id: int,
        kind: NotificationKind,
        payload: Mapping[str, object],
        dedupe_key: str | None,
    ) -> bool:
        """Queue a notice; one with a dedupe key already queued is skipped.

        Args:
            tg_user_id: int - Whom to tell.
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of its text.
            dedupe_key: str | None - What makes a repeat a repeat.

        Returns:
            bool - False when it was a repeat and nothing was queued.

        """
        ...

    async def pending(self, limit: int) -> Sequence[Notice]:
        """Take the oldest notices to send, locked against other workers.

        Args:
            limit: int - How many.

        Returns:
            Sequence[Notice] - The notices.

        """
        ...

    async def sent(self, notice_id: int, now: datetime) -> None:
        """Mark a notice sent.

        Args:
            notice_id: int - The notice.
            now: datetime - When.

        """
        ...

    async def failed(self, notice_id: int, error: str, *, give_up: bool) -> None:
        """Count a failed delivery.

        Args:
            notice_id: int - The notice.
            error: str - What went wrong, without personal data.
            give_up: bool - Never try this notice again.

        """
        ...

    async def purge(self, before: datetime) -> int:
        """Delete sent or abandoned notices created before a moment.

        Args:
            before: datetime - The moment.

        Returns:
            int - How many were deleted.

        """
        ...


class Preferences(Protocol):
    """The students' reminder preferences."""

    async def set_reminders(
        self,
        student_ids: Collection[uuid.UUID],
        *,
        enabled: bool,
    ) -> None:
        """Turn reminders on or off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.
            enabled: bool - On or off.

        """
        ...

    async def muted(self, student_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Tell which of the students turned reminders off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.

        Returns:
            set[uuid.UUID] - Those with reminders off.

        """
        ...
