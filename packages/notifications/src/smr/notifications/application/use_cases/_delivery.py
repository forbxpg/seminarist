"""The worker sends what is waiting, and forgets what is old."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, final

from smr.notifications.application.ports import (
    DeliveryError,
    DeliveryGaveUpError,
    DeliveryRetryError,
)
from smr.notifications.domain import render

if TYPE_CHECKING:
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.notifications.application.ports import Outbox, Sender

MAX_ATTEMPTS = 5
BATCH = 25
_KEEP = timedelta(days=30)
_LONGEST_WAIT = 30.0


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    """How a round of delivery went.

    Attributes:
        sent: int - Delivered.
        failed: int - Failed, to retry later.
        gave_up: int - Failed for good.

    """

    sent: int
    failed: int
    gave_up: int


@final
class DeliverPending:
    """Send the oldest waiting notices; each outcome is committed at once."""

    def __init__(
        self,
        outbox: Outbox,
        sender: Sender,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._outbox: Outbox = outbox
        self._sender: Sender = sender
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock

    async def __call__(self) -> DeliveryReport:
        """Send a batch.

        Returns:
            DeliveryReport - What happened.

        """
        sent = failed = gave_up = 0
        async with self._uow:
            for notice in await self._outbox.pending(BATCH):
                try:
                    await self._send(
                        notice.tg_user_id,
                        render(notice.kind, notice.payload),
                    )
                except DeliveryGaveUpError as error:
                    await self._outbox.failed(
                        notice.notice_id,
                        type(error).__name__,
                        give_up=True,
                    )
                    gave_up += 1
                except DeliveryError as error:
                    last = notice.attempts + 1 >= MAX_ATTEMPTS
                    await self._outbox.failed(
                        notice.notice_id,
                        type(error).__name__,
                        give_up=last,
                    )
                    failed += 1
                else:
                    await self._outbox.sent(notice.notice_id, self._clock.now())
                    sent += 1
            await self._uow.commit()
        return DeliveryReport(sent=sent, failed=failed, gave_up=gave_up)

    async def _send(self, tg_user_id: int, text: str) -> None:
        try:
            await self._sender.send(tg_user_id, text)
        except DeliveryRetryError as error:
            await asyncio.sleep(min(error.after_seconds, _LONGEST_WAIT))
            await self._sender.send(tg_user_id, text)


@final
class PurgeOutbox:
    """Sent or abandoned notices older than a month are deleted."""

    def __init__(self, outbox: Outbox, uow: UnitOfWork, clock: Clock) -> None:
        self._outbox: Outbox = outbox
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock

    async def __call__(self) -> int:
        """Delete them.

        Returns:
            int - How many were deleted.

        """
        async with self._uow:
            deleted = await self._outbox.purge(self._clock.now() - _KEEP)
            await self._uow.commit()
        return deleted
