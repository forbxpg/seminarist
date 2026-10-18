"""The grading server's container: the review and the БДЗ that feeds it."""

from __future__ import annotations

from dishka import AsyncContainer, Provider, make_async_container

from smr.bdz.di import BdzProvider
from smr.core.di import CONTAINER_VALIDATION, CoreProvider
from smr.gradebook.di import GradebookProvider
from smr.notifications.di import NotificationsProvider
from smr.review.di import ReviewProvider
from smr.roster.di import RosterProvider


def make_container(*extra: Provider) -> AsyncContainer:
    """Build the server's container.

    Args:
        extra: Provider - Providers that replace settings in a test.

    Returns:
        AsyncContainer - Every use case a tool resolves.

    """
    return make_async_container(
        CoreProvider(),
        RosterProvider(),
        GradebookProvider(),
        NotificationsProvider(),
        ReviewProvider(),
        BdzProvider(),
        *extra,
        validation_settings=CONTAINER_VALIDATION,
    )
