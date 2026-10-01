"""Notifications' repositories, contract and use cases, for every app.

The `Sender` is not here: only the worker delivers, and it provides its own.
"""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.application.ports import Outbox, Preferences
from smr.notifications.application.services import Notifier
from smr.notifications.application.use_cases import (
    DeliverPending,
    PurgeOutbox,
    RemindersEnabled,
    SetReminders,
)
from smr.notifications.infrastructure.repositories import (
    SqlAlchemyOutbox,
    SqlAlchemyPreferences,
)


@final
class NotificationsProvider(Provider):
    """Everything of notifications, built per update or task."""

    scope = Scope.REQUEST

    outbox = provide(SqlAlchemyOutbox, provides=Outbox)
    preferences = provide(SqlAlchemyPreferences, provides=Preferences)
    api = provide(Notifier, provides=NotificationsApi)

    use_cases = provide_all(DeliverPending, PurgeOutbox, RemindersEnabled, SetReminders)
