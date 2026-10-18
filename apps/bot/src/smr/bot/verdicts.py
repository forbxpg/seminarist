"""The student's breakdown of a verdict, split under Telegram's limit."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from smr.bot.texts import safe

if TYPE_CHECKING:
    from smr.review.application.use_cases import VerdictView

_CENT = Decimal("0.01")


def verdict_messages(
    view: VerdictView,
    *,
    title: str,
    limit: int = 4096,
) -> list[str]:
    """Build the HTML messages, one block per task, never cut in the middle.

    Args:
        view: VerdictView - The current verdict.
        title: str - The БДЗ title.
        limit: int - The most characters in one message.

    Returns:
        list[str] - Messages. A block longer than `limit` is cut and ends with "…".

    """
    verdict = view.verdict
    blocks = [
        (
            f"<b>{safe(title)}</b>: {_points(verdict.total)} из "
            f"{_points(verdict.max_points)}"
        ),
    ]
    if verdict.summary:
        blocks.append(safe(verdict.summary))
    for task in verdict.tasks:
        line = (
            f"Задача {task.number}: {_points(task.points)} из "
            f"{_points(task.max_points)} — {safe(task.explanation)}"
        )
        if task.unreadable:
            line += " (не удалось прочитать)"
        if task.manipulation:
            line += " (обращение к проверяющему — 0)"
        blocks.append(line)
    return _pack(blocks, limit)


def _points(value: Decimal) -> str:
    text = format(value.quantize(_CENT), "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def _pack(blocks: list[str], limit: int) -> list[str]:
    messages: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > limit:
            if current:
                messages.append(current)
                current = ""
            messages.append(block[: limit - 1] + "…")
            continue
        joined = block if not current else f"{current}\n\n{block}"
        if len(joined) <= limit:
            current = joined
            continue
        messages.append(current)
        current = block
    if current:
        messages.append(current)
    return messages
