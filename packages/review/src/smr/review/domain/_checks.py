"""Whether a verdict may be stored, and which status it gets."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from ._enums import VerdictStatus
from ._errors import VerdictRejectedError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._entities import SchemeTask, TaskVerdict

APPEAL_WINDOW = timedelta(days=7)
_CENT = Decimal("0.01")
_EXPLANATION_LIMIT = 1500


def check_tasks(
    tasks: Sequence[TaskVerdict],
    scheme: Sequence[SchemeTask],
    pages: int,
) -> None:
    """Check task rows against the scheme and the work's pages.

    Args:
        tasks: Sequence[TaskVerdict] - The rows.
        scheme: Sequence[SchemeTask] - The assignment's tasks.
        pages: int - How many pages the work has.

    Raises:
        VerdictRejectedError: If a row is missing, extra, duplicate, or out of range.

    """
    numbers = [task.number for task in tasks]
    duplicates = sorted(
        {number for number in numbers if numbers.count(number) > 1},
    )
    if duplicates:
        msg = f"duplicate tasks: {duplicates}"
        raise VerdictRejectedError(msg)
    expected = [item.number for item in scheme]
    missing = [number for number in expected if number not in numbers]
    if missing:
        msg = f"missing tasks: {missing}"
        raise VerdictRejectedError(msg)
    extra = [number for number in numbers if number not in expected]
    if extra:
        msg = f"extra tasks: {extra}"
        raise VerdictRejectedError(msg)
    limits = {item.number: item.max_points for item in scheme}
    for task in tasks:
        _check_task(task, limits[task.number], pages)


def check_pages_seen(pages_seen: Sequence[int], pages: int) -> None:
    """Require every page of the work, whatever the order.

    Args:
        pages_seen: Sequence[int] - Pages the grader claims to have read.
        pages: int - How many pages the work has.

    Raises:
        VerdictRejectedError: If any page is missing.

    """
    if sorted(set(pages_seen)) != list(range(1, pages + 1)):
        msg = f"pages seen must be 1..{pages}"
        raise VerdictRejectedError(msg)


def status_for(tasks: Sequence[TaskVerdict]) -> VerdictStatus:
    """Choose published or manual from the flags.

    Args:
        tasks: Sequence[TaskVerdict] - The rows.

    Returns:
        VerdictStatus - Manual when any task is unreadable or unsure.

    """
    if any(task.unreadable or task.unsure for task in tasks):
        return VerdictStatus.MANUAL
    return VerdictStatus.PUBLISHED


def appeal_open_until(published_at: datetime) -> datetime:
    """Tell the last moment an appeal is still in time.

    Args:
        published_at: datetime - When the student was told the grade.

    Returns:
        datetime - Seven days later.

    """
    return published_at + APPEAL_WINDOW


def _check_task(task: TaskVerdict, limit: Decimal, pages: int) -> None:
    """Refuse one row that breaks a rule.

    Args:
        task: TaskVerdict - The row.
        limit: Decimal - The scheme's maximum for it.
        pages: int - How many pages the work has.

    Raises:
        VerdictRejectedError: If the row is out of range.

    """
    if task.points < 0:
        msg = f"task {task.number}: points {task.points} below 0"
        raise VerdictRejectedError(msg)
    if task.points > limit:
        msg = f"task {task.number}: points {task.points} above max {limit}"
        raise VerdictRejectedError(msg)
    if task.points != task.points.quantize(_CENT):
        msg = f"task {task.number}: more than 2 decimals"
        raise VerdictRejectedError(msg)
    if task.manipulation and task.points != 0:
        msg = f"task {task.number}: manipulation scores 0"
        raise VerdictRejectedError(msg)
    explanation = task.explanation.strip()
    if not explanation:
        msg = f"task {task.number}: explanation is empty"
        raise VerdictRejectedError(msg)
    if len(explanation) > _EXPLANATION_LIMIT:
        msg = f"task {task.number}: explanation is too long"
        raise VerdictRejectedError(msg)
    for page in task.pages:
        if page < 1 or page > pages:
            msg = f"task {task.number}: page {page}"
            raise VerdictRejectedError(msg)
