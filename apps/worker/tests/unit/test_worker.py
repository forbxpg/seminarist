"""The worker's wiring and its pieces."""

from __future__ import annotations

import importlib
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.methods import SendMessage

from smr.core.clock import FixedClock
from smr.notifications.application.ports import (
    DeliveryError,
    DeliveryGaveUpError,
    DeliveryRetryError,
)
from smr.worker.di import make_container
from smr.worker.tasks import delete_old_exports
from smr.worker.telegram import TelegramSender

if TYPE_CHECKING:
    from pathlib import Path

_METHOD = SendMessage(chat_id=1, text="x")


class _Bot:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.sent: list[int] = []

    async def send_message(self, chat_id: int, _text: str, **_: object) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(chat_id)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TelegramRetryAfter(_METHOD, "flood", 3), DeliveryRetryError),
        (
            TelegramForbiddenError(_METHOD, "Forbidden: bot was blocked by the user"),
            DeliveryGaveUpError,
        ),
        (
            TelegramBadRequest(_METHOD, "Bad Request: chat not found"),
            DeliveryGaveUpError,
        ),
        (
            TelegramBadRequest(_METHOD, "Bad Request: can't parse entities"),
            DeliveryError,
        ),
    ],
)
async def test_telegram_failures_are_told_apart(
    error: Exception,
    expected: type[Exception],
) -> None:
    """Each Telegram failure becomes the delivery error the outbox acts on."""
    sender = TelegramSender(_Bot(error))  # pyright: ignore[reportArgumentType] -- a stand-in bot
    with pytest.raises(expected):
        await sender.send(1, "x")


async def test_retry_after_carries_the_wait() -> None:
    """The wait Telegram asked for reaches the outbox."""
    sender = TelegramSender(_Bot(TelegramRetryAfter(_METHOD, "flood", 7)))  # pyright: ignore[reportArgumentType] -- a stand-in bot
    with pytest.raises(DeliveryRetryError) as caught:
        await sender.send(1, "x")
    assert caught.value.after_seconds == 7


def test_old_exports_are_deleted(tmp_path: Path) -> None:
    """Exports older than the retention go; newer ones stay."""
    now = datetime(2026, 10, 2, tzinfo=UTC)
    old, new = tmp_path / "old.zip", tmp_path / "new.zip"
    for path, age in ((old, timedelta(days=20)), (new, timedelta(days=1))):
        path.write_bytes(b"x")
        moment = (now - age).timestamp()
        os.utime(path, (moment, moment))
    assert delete_old_exports(tmp_path, FixedClock(now), timedelta(days=14)) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["new.zip"]


def test_the_container_is_complete() -> None:
    """Every task's dependencies can be built: the graph validates without a database."""
    container = make_container()
    assert container is not None


def test_the_broker_registers_the_scheduled_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker module knows the four tasks and the scheduler reads their labels."""
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PASSWORD", "x")
    module = importlib.import_module("smr.worker.broker")
    names = set(module.broker.get_all_tasks())
    assert {"deliver_outbox", "queue_reminders", "back_up", "purge_expired"} <= names
