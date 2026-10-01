"""PostgreSQL connection settings."""

from __future__ import annotations

from typing import ClassVar

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class DatabaseSettings(BaseSettings):
    """Database settings.

    Attributes:
        url: PostgresDsn - Connection URL, `postgresql+asyncpg://...`.
        echo: bool - Log every SQL statement.
        pool_size: int - Connections kept open per process.
        max_overflow: int - Connections allowed above the pool size.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("DATABASE_")

    url: PostgresDsn
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 5
