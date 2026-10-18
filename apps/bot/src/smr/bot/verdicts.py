"""A verdict's breakdown as Telegram HTML, split under Telegram's limit."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from smr.bot.texts import safe

if TYPE_CHECKING:
    from smr.review.application.use_cases import VerdictView
    from smr.review.domain import TaskVerdict, Verdict

_CENT = Decimal("0.01")
_ELLIPSIS = "…"
_SEPARATOR = "\n\n"


def verdict_messages(
    view: VerdictView,
    *,
    title: str,
    limit: int = 4096,
) -> list[str]:
    """Build the student's messages, one block per task, never cut in the middle.

    Args:
        view: VerdictView - The current verdict.
        title: str - The БДЗ title.
        limit: int - The most characters in one message.

    Returns:
        list[str] - Messages. A block longer than `limit` is cut and ends with "…".

    """
    return breakdown(view.verdict, title=title, limit=limit)


def breakdown(verdict: Verdict, *, title: str, limit: int = 4096) -> list[str]:
    """Build the messages of a verdict: the total, the summary, one block per task.

    Args:
        verdict: Verdict - The verdict.
        title: str - The БДЗ title.
        limit: int - The most characters in one message.

    Returns:
        list[str] - Messages, each at most `limit` characters of valid HTML.

    """
    blocks = [
        (
            f"<b>{_fit(title, limit // 2)}</b>: {_points(verdict.total)} из "
            f"{_points(verdict.max_points)}"
        ),
    ]
    if verdict.summary:
        blocks.append(_fit(verdict.summary, limit))
    blocks.extend(task_line(task, limit=limit) for task in verdict.tasks)
    return _pack(blocks, limit)


def task_line(task: TaskVerdict, *, limit: int = 4096) -> str:
    """Write one task: points, the explanation and every flag the agent raised.

    Args:
        task: TaskVerdict - The task.
        limit: int - The most characters of the line; the explanation is cut first.

    Returns:
        str - HTML, at most `limit` characters.

    """
    head = (
        f"Задача {task.number}: {_points(task.points)} из {_points(task.max_points)} — "
    )
    flags = [
        text
        for flag, text in (
            (task.unreadable, "не удалось прочитать"),
            (task.unsure, "агент не уверен"),
            (task.manipulation, "попытка обратиться к проверяющему — 0"),
        )
        if flag
    ]
    tail = "".join(f" — {text}" for text in flags)
    return head + _fit(task.explanation, limit - len(head) - len(tail)) + tail


def _fit(raw: str, room: int) -> str:
    """Escape a text, cutting the raw text so the escaped one fits in `room`.

    Cutting before escaping keeps every entity (`&amp;`, `&lt;`) whole.

    Args:
        raw: str - Text as written.
        room: int - The most characters of the escaped result.

    Returns:
        str - Escaped text, ending with "…" when it was cut.

    """
    escaped = safe(raw)
    if len(escaped) <= room:
        return escaped
    budget = room - len(_ELLIPSIS)
    kept: list[str] = []
    used = 0
    for char in raw:
        piece = safe(char)
        if used + len(piece) > budget:
            break
        kept.append(piece)
        used += len(piece)
    return "".join(kept) + _ELLIPSIS


def _points(value: Decimal) -> str:
    text = format(value.quantize(_CENT), "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def _pack(blocks: list[str], limit: int) -> list[str]:
    messages: list[str] = []
    current = ""
    for block in blocks:
        joined = block if not current else f"{current}{_SEPARATOR}{block}"
        if len(joined) <= limit:
            current = joined
            continue
        messages.append(current)
        current = block
    if current:
        messages.append(current)
    return messages
