"""The worker's own dependencies: the bot that sends, the sender, the backup."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import final

from aiogram import Bot
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from smr.bdz.application.services import BdzReviewSource
from smr.bdz.di import BdzProvider
from smr.core.backup import Backup
from smr.core.clock import Clock
from smr.core.config import DatabaseSettings, StorageSettings, TelegramSettings
from smr.core.di import CONTAINER_VALIDATION, CoreProvider
from smr.gradebook.di import GradebookProvider
from smr.homework.application.services import HomeworkReviewSource
from smr.homework.di import HomeworkProvider
from smr.materials.di import MaterialsProvider
from smr.notifications.application.ports import Sender
from smr.notifications.application.use_cases import DeliverPending
from smr.notifications.di import NotificationsProvider
from smr.review.application.ports import ReviewSource
from smr.review.di import ReviewProvider
from smr.roster.di import RosterProvider

from .telegram import TelegramSender


@final
class WorkerProvider(Provider):
    """What only the worker needs."""

    @provide(scope=Scope.APP)
    async def bot(self, settings: TelegramSettings) -> AsyncIterator[Bot]:
        """Open the bot that sends the notices.

        Args:
            settings: TelegramSettings - The token.

        Yields:
            Bot - The bot; its HTTP session is closed on shutdown.

        """
        bot = Bot(settings.bot_token.get_secret_value())
        yield bot
        await bot.session.close()

    @provide(scope=Scope.APP)
    def sender(self, bot: Bot) -> Sender:
        """Send through Telegram.

        Args:
            bot: Bot - The bot.

        Returns:
            Sender - The sender.

        """
        return TelegramSender(bot)

    deliver = provide(DeliverPending, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def backup(
        self,
        database: DatabaseSettings,
        storage: StorageSettings,
        clock: Clock,
    ) -> Backup:
        """Back up the database and the files.

        Args:
            database: DatabaseSettings - What to dump.
            storage: StorageSettings - What to pack and where to put it.
            clock: Clock - The clock.

        Returns:
            Backup - The backup.

        """
        return Backup(str(database.url), storage.data_dir, storage.backup_dir, clock)


@final
class ReviewSourcesProvider(Provider):
    """БДЗ and ordinary homework, for the review."""

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


def make_container() -> AsyncContainer:
    """Build the worker's container.

    Returns:
        AsyncContainer - Every provider the tasks need.

    """
    return make_async_container(
        CoreProvider(),
        RosterProvider(),
        GradebookProvider(),
        NotificationsProvider(),
        HomeworkProvider(),
        MaterialsProvider(),
        ReviewProvider(),
        BdzProvider(),
        ReviewSourcesProvider(),
        WorkerProvider(),
        validation_settings=CONTAINER_VALIDATION,
    )
