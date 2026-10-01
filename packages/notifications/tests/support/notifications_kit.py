"""Notifications over one session, with a sender that records what it sends."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from sqlalchemy import select

from smr.core.access import AdminGuard
from smr.core.database import SqlAlchemyUnitOfWork
from smr.notifications.application.ports import DeliveryGaveUpError, DeliveryRetryError
from smr.notifications.application.services import Notifier
from smr.notifications.application.use_cases import DeliverPending, SetReminders
from smr.notifications.infrastructure.models import OutboxModel
from smr.notifications.infrastructure.repositories import (
    SqlAlchemyOutbox,
    SqlAlchemyPreferences,
)
from smr.roster.application.use_cases import Memberships
from smr.roster.infrastructure.repositories import SqlAlchemyGroups, SqlAlchemyStudents

if TYPE_CHECKING:
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("FakeSender", "Notifications", "notifications")


@final
class FakeSender:
    """Records the texts it is asked to send; can be told to fail for an account."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.blocked: set[int] = set()
        self.busy_once: set[int] = set()

    async def send(self, tg_user_id: int, text: str) -> None:
        """Send, or fail the way Telegram would."""
        if tg_user_id in self.blocked:
            raise DeliveryGaveUpError
        if tg_user_id in self.busy_once:
            self.busy_once.discard(tg_user_id)
            raise DeliveryRetryError(0)
        self.sent.append((tg_user_id, text))


@final
class Notifications:
    """The notifier, the delivery and the preferences over one session."""

    def __init__(self, session: AsyncSession, roster: Roster) -> None:
        outbox = SqlAlchemyOutbox(session)
        preferences = SqlAlchemyPreferences(session)
        uow = SqlAlchemyUnitOfWork(session)
        self.session: AsyncSession = session
        self.sender: FakeSender = FakeSender()
        self.notifier: Notifier = Notifier(
            outbox,
            preferences,
            roster.api,
            AdminGuard({1}),
        )
        self.deliver: DeliverPending = DeliverPending(
            outbox,
            self.sender,
            uow,
            roster.clock,
        )
        memberships = Memberships(
            SqlAlchemyGroups(session),
            SqlAlchemyStudents(session),
        )
        self.set_reminders: SetReminders = SetReminders(memberships, preferences, uow)

    async def queued(self) -> list[OutboxModel]:
        """Read the whole outbox."""
        return list(
            await self.session.scalars(select(OutboxModel).order_by(OutboxModel.id)),
        )


@pytest.fixture
def notifications(session: AsyncSession, roster: Roster) -> Notifications:
    """Give notifications over the test's session."""
    return Notifications(session, roster)
