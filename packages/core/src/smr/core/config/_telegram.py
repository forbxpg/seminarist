"""Telegram bot settings: the token and who the teachers are."""

from __future__ import annotations

from typing import Annotated, ClassVar

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from ._base import settings_config


class TelegramSettings(BaseSettings):
    """Telegram settings.

    Attributes:
        bot_token: SecretStr - Token from @BotFather.
        admin_ids: frozenset[int] - Telegram user ids with full teacher rights.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("TELEGRAM_")

    bot_token: SecretStr
    admin_ids: Annotated[frozenset[int], NoDecode]

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        """Read `TELEGRAM_ADMIN_IDS` as comma-separated ids, not as JSON.

        Args:
            value: object - The raw environment value.

        Returns:
            object - A set of ids for a string, the value untouched otherwise.

        """
        if isinstance(value, str):
            return frozenset(int(part) for part in value.split(",") if part.strip())
        return value
