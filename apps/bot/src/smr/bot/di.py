"""The bot's container: every package's providers and the bot itself."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import final

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from smr.bdz.di import BdzProvider
from smr.core.backup import Backup
from smr.core.clock import Clock
from smr.core.config import DatabaseSettings, StorageSettings, TelegramSettings
from smr.core.di import CONTAINER_VALIDATION, CoreProvider
from smr.gradebook.di import GradebookProvider
from smr.homework.di import HomeworkProvider
from smr.materials.di import MaterialsProvider
from smr.notifications.di import NotificationsProvider
from smr.review.di import ReviewProvider
from smr.roster.di import RosterProvider
from smr.sessions.di import SessionsProvider


@final
class BotProvider(Provider):
    """What only the bot needs."""

    @provide(scope=Scope.APP)
    async def bot(self, settings: TelegramSettings) -> AsyncIterator[Bot]:
        """Open the bot.

        Args:
            settings: TelegramSettings - The token.

        Yields:
            Bot - The bot, HTML by default; its session is closed on shutdown.

        """
        bot = Bot(
            settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        yield bot
        await bot.session.close()

    @provide(scope=Scope.APP)
    def backup(
        self,
        database: DatabaseSettings,
        storage: StorageSettings,
        clock: Clock,
    ) -> Backup:
        """Back up on the teacher's request.

        Args:
            database: DatabaseSettings - What to dump.
            storage: StorageSettings - What to pack and where.
            clock: Clock - The clock.

        Returns:
            Backup - The backup.

        """
        return Backup(str(database.url), storage.data_dir, storage.backup_dir, clock)


def make_container() -> AsyncContainer:
    """Build the bot's container.

    Returns:
        AsyncContainer - Every provider the handlers and dialogs need.

    """
    return make_async_container(
        CoreProvider(),
        RosterProvider(),
        GradebookProvider(),
        NotificationsProvider(),
        SessionsProvider(),
        HomeworkProvider(),
        MaterialsProvider(),
        ReviewProvider(),
        BdzProvider(),
        BotProvider(),
        validation_settings=CONTAINER_VALIDATION,
    )
