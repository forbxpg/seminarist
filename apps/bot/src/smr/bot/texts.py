"""Texts shown to people, and how values are written in them."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from smr.core.clock import MOSCOW

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

CONSENT_VERSION = "2026-10-02"

CONSENT = (
    "<b>Обработка персональных данных</b>\n\n"
    "Бот хранит ваше ФИО из списка группы, ваш Telegram ID, сданные работы и баллы, "
    "чтобы преподаватель вёл учёт по семинарам. Данные лежат на компьютере "
    "преподавателя и никому не передаются. Удалить их можно в «Настройках» "
    "(«Удалить мои данные»); после окончания семестра они удаляются автоматически."
)


def moment(value: datetime) -> str:
    """Write a moment as Moscow time.

    Args:
        value: datetime - An aware moment.

    Returns:
        str - "07.10 23:59".

    """
    return f"{value.astimezone(MOSCOW):%d.%m %H:%M}"


def points(value: Decimal) -> str:
    """Write points without trailing zeros.

    Args:
        value: Decimal - Points.

    Returns:
        str - "2.5", "3".

    """
    normalized = value.normalize()
    return f"{normalized:f}"


def safe(value: object) -> str:
    """Escape a value for Telegram HTML.

    Args:
        value: object - Anything.

    Returns:
        str - Its text, escaped.

    """
    return escape(str(value))
