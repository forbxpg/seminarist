"""Deliver notices through the Telegram Bot API."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)

from smr.notifications.application.ports import (
    DeliveryError,
    DeliveryGaveUpError,
    DeliveryRetryError,
)

if TYPE_CHECKING:
    from aiogram import Bot

_UNREACHABLE = ("chat not found", "user is deactivated", "bot was blocked")


@final
class TelegramSender:
    """`Sender` over aiogram's `Bot`, Telegram's failures told apart."""

    def __init__(self, bot: Bot) -> None:
        self._bot: Bot = bot

    async def send(self, tg_user_id: int, text: str) -> None:
        """Send a text.

        Args:
            tg_user_id: int - The account.
            text: str - Telegram HTML.

        Raises:
            DeliveryRetryError: When Telegram asks to wait.
            DeliveryGaveUpError: When the account cannot be reached at all.
            DeliveryError: On any other failure.

        """
        try:
            _ = await self._bot.send_message(
                tg_user_id,
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except TelegramRetryAfter as error:
            raise DeliveryRetryError(float(error.retry_after)) from error
        except TelegramForbiddenError as error:
            raise DeliveryGaveUpError from error
        except TelegramBadRequest as error:
            if any(reason in error.message.lower() for reason in _UNREACHABLE):
                raise DeliveryGaveUpError from error
            raise DeliveryError from error
        except (TelegramNetworkError, TelegramAPIError) as error:
            raise DeliveryError from error
