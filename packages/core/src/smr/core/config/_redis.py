"""Redis connection settings."""

from __future__ import annotations

from typing import ClassVar

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class RedisSettings(BaseSettings):
    """Redis settings.

    Attributes:
        host: str - Redis host.
        port: int - Redis port.
        password: SecretStr - Password; Redis always requires one here.
        fsm_db: int - Logical database of the dialog state.
        tasks_db: int - Logical database of the task queue.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("REDIS_")

    host: str
    port: int = 6379
    password: SecretStr
    fsm_db: int = 0
    tasks_db: int = 1

    def url(self, db: int) -> str:
        """Build the connection URL of a logical database.

        Args:
            db: int - Logical database number.

        Returns:
            str - `redis://:<password>@<host>:<port>/<db>`.

        """
        password = self.password.get_secret_value()
        return f"redis://:{password}@{self.host}:{self.port}/{db}"
