"""Assemble the dispatcher and run the bot by long polling."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from aiogram_dialog import setup_dialogs
from dishka.integrations.aiogram import setup_dishka

from smr.bot.dialogs.admin import admin_dialogs
from smr.bot.dialogs.student.consent import consent_dialog
from smr.bot.dialogs.student.join import join_dialog
from smr.bot.dialogs.student.menu import student_dialog
from smr.bot.handlers.bindings import router as bindings_router
from smr.bot.handlers.errors import router as errors_router
from smr.bot.handlers.start import router as start_router
from smr.bot.middlewares import ConsentMiddleware, GateMiddleware
from smr.core.access import AdminGuard
from smr.core.config import RedisSettings

if TYPE_CHECKING:
    from aiogram.fsm.storage.base import BaseStorage
    from aiogram_dialog.api.protocols import MessageManagerProtocol
    from dishka import AsyncContainer


logger = logging.getLogger(__name__)


def build_dispatcher(
    container: AsyncContainer,
    storage: BaseStorage,
    guard: AdminGuard,
    message_manager: MessageManagerProtocol | None = None,
) -> Dispatcher:
    """Put the routers, dialogs, middlewares and DI together.

    Args:
        container: AsyncContainer - The dependencies.
        storage: BaseStorage - Where dialog state lives.
        guard: AdminGuard - Who the teachers are.
        message_manager: MessageManagerProtocol | None - Where dialog texts go;
            the real Telegram sender when omitted.

    Returns:
        Dispatcher - Ready to poll.

    """
    dispatcher = Dispatcher(storage=storage)
    gate = GateMiddleware(guard)
    _ = dispatcher.message.outer_middleware(gate)
    _ = dispatcher.callback_query.outer_middleware(gate)
    dispatcher.include_routers(errors_router, start_router, bindings_router)
    dispatcher.include_routers(
        join_dialog,
        student_dialog,
        consent_dialog,
        *admin_dialogs(),
    )
    _ = setup_dialogs(dispatcher, message_manager=message_manager)
    setup_dishka(container, router=dispatcher, auto_inject=True)
    consent = ConsentMiddleware()
    _ = dispatcher.message.middleware(consent)
    _ = dispatcher.callback_query.middleware(consent)
    return dispatcher


async def run() -> None:
    """Poll Telegram until stopped."""
    from smr.bot.di import make_container  # ruff: ignore[import-outside-top-level] -- the container reads the environment

    container = make_container()
    redis = RedisSettings()  # pyright: ignore[reportCallIssue] -- required, read from the environment
    storage = RedisStorage.from_url(
        redis.url(redis.fsm_db),
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )
    guard = await container.get(AdminGuard)
    bot = await container.get(Bot)
    dispatcher = build_dispatcher(container, storage, guard)
    _ = await bot.set_my_commands(
        [BotCommand(command="start", description="Меню")],
    )
    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await storage.close()
        await container.close()


def main() -> None:
    """Run the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


__all__ = ("build_dispatcher", "main")
