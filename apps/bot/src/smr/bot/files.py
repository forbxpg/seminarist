"""Take a file a person sent: its bytes and Telegram's ids, within the limit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from smr.core.files import FileKind, FileTooLargeError

if TYPE_CHECKING:
    from datetime import datetime

    from aiogram import Bot
    from aiogram.types import MaybeInaccessibleMessageUnion

TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Received:
    """A file received from a person.

    Attributes:
        data: bytes - Its content.
        tg_file_id: str - Telegram's id.
        tg_file_unique_id: str - Telegram's stable id.
        sent_at: datetime - The message's date.

    """

    data: bytes
    tg_file_id: str
    tg_file_unique_id: str
    sent_at: datetime


async def receive(bot: Bot, message: Message) -> Received | None:
    """Download the photo or document of a message.

    Args:
        bot: Bot - The bot.
        message: Message - The message.

    Returns:
        Received | None - The file; none when the message carries neither.

    Raises:
        FileTooLargeError: If Telegram would not let the bot download it.

    """
    if message.photo:
        biggest = message.photo[-1]
        file_id, unique_id, size = (
            biggest.file_id,
            biggest.file_unique_id,
            biggest.file_size,
        )
    elif message.document:
        document = message.document
        file_id, unique_id, size = (
            document.file_id,
            document.file_unique_id,
            document.file_size,
        )
    else:
        return None
    if size is not None and size > TELEGRAM_DOWNLOAD_LIMIT:
        raise FileTooLargeError
    downloaded = await bot.download(file_id)
    if downloaded is None:
        return None
    return Received(downloaded.read(), file_id, unique_id, message.date)


async def send_file(
    message: MaybeInaccessibleMessageUnion | None,
    tg_file_id: str,
    kind: FileKind,
    caption: str | None = None,
) -> None:
    """Send a stored file back: an image as a photo if Telegram allows, else a document.

    A file id remembers how the file came in: a photo's id cannot be sent as a document
    and the other way round, so an image is tried as a photo first.

    Args:
        message: MaybeInaccessibleMessageUnion | None - Where to answer; nothing is sent
            when the message is gone or too old for the bot to see.
        tg_file_id: str - Telegram's id of the file.
        kind: FileKind - What the file is.
        caption: str | None - A caption.

    """
    if not isinstance(message, Message):
        return
    if kind.is_image:
        try:
            _ = await message.answer_photo(tg_file_id, caption=caption)
        except TelegramBadRequest:
            pass
        else:
            return
    _ = await message.answer_document(tg_file_id, caption=caption)
