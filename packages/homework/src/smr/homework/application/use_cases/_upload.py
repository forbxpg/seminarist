"""A file as the bot hands it over: its bytes and Telegram's facts about it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Upload:
    """A file a person sent to the bot.

    Attributes:
        data: bytes - Its content.
        tg_file_id: str - Telegram's id, to send it again.
        tg_file_unique_id: str - Telegram's stable id.
        sent_at: datetime - The message's date, by Telegram's clock.

    """

    data: bytes
    tg_file_id: str
    tg_file_unique_id: str
    sent_at: datetime
