"""The texts of notices, in Russian, as Telegram HTML."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import TYPE_CHECKING

from smr.core.clock import MOSCOW

from ._kinds import NotificationKind

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def _text(payload: Mapping[str, object], key: str) -> str:
    return escape(str(payload.get(key, "")))


def _moment(payload: Mapping[str, object], key: str) -> str:
    raw = payload.get(key)
    if not isinstance(raw, str):
        return ""
    return f"{datetime.fromisoformat(raw).astimezone(MOSCOW):%d.%m %H:%M}"


def _assignment(p: Mapping[str, object]) -> str:
    return (
        f"📝 Новое домашнее задание: <b>{_text(p, 'title')}</b>\n"
        f"Срок: {_moment(p, 'deadline')} (МСК)\n"
        f"Группа: {_text(p, 'group')}"
    )


def _material(p: Mapping[str, object]) -> str:
    return (
        f"📚 Опубликован материал: <b>{_text(p, 'title')}</b>\n"
        f"Группа: {_text(p, 'group')}\n"
        "Откройте «Семинары» в меню."
    )


def _graded(p: Mapping[str, object]) -> str:
    comment = p.get("comment")
    tail = f"\nКомментарий: {escape(str(comment))}" if comment else ""
    return (
        f"✅ Проверено: <b>{_text(p, 'title')}</b>\n"
        f"Баллы: {_text(p, 'points')} из {_text(p, 'max_points')}{tail}"
    )


def _reminder(p: Mapping[str, object]) -> str:
    return (
        f"⏰ Напоминание: <b>{_text(p, 'title')}</b> нужно сдать "
        f"до {_moment(p, 'deadline')} (МСК).\n"
        "Отключить напоминания можно в «Настройках»."
    )


def _binding_requested(p: Mapping[str, object]) -> str:
    return (
        f"🙋 Заявка на привязку в группе {_text(p, 'group')}: "
        f"<b>{_text(p, 'name')}</b>. Откройте «Заявки» в /admin."
    )


def _binding_approved(p: Mapping[str, object]) -> str:
    return (
        f"🎉 Преподаватель подтвердил вас в группе {_text(p, 'group')}. Нажмите /start."
    )


def _binding_rejected(p: Mapping[str, object]) -> str:
    return (
        f"Преподаватель отклонил привязку в группе {_text(p, 'group')}. "
        "Если это ошибка, выберите свою фамилию снова по ссылке группы."
    )


_RENDERERS: dict[NotificationKind, Callable[[Mapping[str, object]], str]] = {
    NotificationKind.ASSIGNMENT_PUBLISHED: _assignment,
    NotificationKind.MATERIAL_PUBLISHED: _material,
    NotificationKind.HOMEWORK_GRADED: _graded,
    NotificationKind.DEADLINE_REMINDER: _reminder,
    NotificationKind.BINDING_REQUESTED: _binding_requested,
    NotificationKind.BINDING_APPROVED: _binding_approved,
    NotificationKind.BINDING_REJECTED: _binding_rejected,
}


def render(kind: NotificationKind, payload: Mapping[str, object]) -> str:
    """Write a notice's text.

    Args:
        kind: NotificationKind - What it is about.
        payload: Mapping[str, object] - Its values.

    Returns:
        str - Telegram HTML; every value escaped.

    """
    return _RENDERERS[kind](payload)
