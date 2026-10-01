"""Reading the settings from the environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from smr.core.config import RedisSettings, TelegramSettings

if TYPE_CHECKING:
    import pytest


def test_admin_ids_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    """`TELEGRAM_ADMIN_IDS=1, 2` gives two ids."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "1, 2")
    assert TelegramSettings().admin_ids == frozenset({1, 2})  # pyright: ignore[reportCallIssue]


def test_redis_url_carries_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """The URL of a logical database carries the password."""
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PASSWORD", "s3cret")
    settings = RedisSettings()  # pyright: ignore[reportCallIssue]
    assert settings.url(1) == "redis://:s3cret@redis:6379/1"
