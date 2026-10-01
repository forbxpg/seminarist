"""Settings read from the environment, one class per concern."""

from __future__ import annotations

from ._base import settings_config
from ._database import DatabaseSettings
from ._redis import RedisSettings
from ._storage import StorageSettings
from ._telegram import TelegramSettings

__all__ = (
    "DatabaseSettings",
    "RedisSettings",
    "StorageSettings",
    "TelegramSettings",
    "settings_config",
)
