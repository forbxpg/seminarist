"""The grading server's container: the review and the БДЗ that feeds it."""

from __future__ import annotations

from collections.abc import Sequence
from typing import final

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from smr.bdz.application.services import BdzReviewSource
from smr.bdz.di import BdzProvider
from smr.core.di import CONTAINER_VALIDATION, CoreProvider
from smr.gradebook.di import GradebookProvider
from smr.homework.application.services import HomeworkReviewSource
from smr.homework.di import HomeworkProvider
from smr.notifications.di import NotificationsProvider
from smr.review.application.ports import ReviewSource
from smr.review.di import ReviewProvider
from smr.roster.di import RosterProvider


@final
class ReviewSourcesProvider(Provider):
    """БДЗ and ordinary homework, for the grading agent."""

    scope = Scope.REQUEST

    @provide
    def review_sources(
        self,
        bdz: BdzReviewSource,
        homework: HomeworkReviewSource,
    ) -> Sequence[ReviewSource]:
        """Give the review both sources.

        Args:
            bdz: BdzReviewSource - БДЗ.
            homework: HomeworkReviewSource - Ordinary homework. The agent skips
                it unless the teacher names the source.

        Returns:
            Sequence[ReviewSource] - БДЗ, then homework.

        """
        return (bdz, homework)


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
        HomeworkProvider(),
        ReviewSourcesProvider(),
        *extra,
        validation_settings=CONTAINER_VALIDATION,
    )
