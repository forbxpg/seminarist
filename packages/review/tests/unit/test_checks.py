"""The checks a verdict must pass before it is stored."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from smr.review.domain import (
    SchemeTask,
    TaskVerdict,
    VerdictRejectedError,
    VerdictStatus,
    appeal_open_until,
    check_pages_seen,
    check_tasks,
    status_for,
)

_SCHEME = (
    SchemeTask(1, Decimal(3)),
    SchemeTask(2, Decimal(5)),
    SchemeTask(3, Decimal(2)),
)


def _task(
    number: int,
    points: str,
    *,
    max_points: str = "5",
    explanation: str = "Верно.",
    unreadable: bool = False,
    unsure: bool = False,
    manipulation: bool = False,
    pages: tuple[int, ...] = (1,),
) -> TaskVerdict:
    return TaskVerdict(
        number,
        Decimal(points),
        Decimal(max_points),
        explanation,
        unreadable,
        unsure,
        manipulation,
        pages,
    )


def test_missing_task_refused() -> None:
    """A scheme task with no row is refused."""
    with pytest.raises(VerdictRejectedError, match=r"missing tasks: \[3\]"):
        check_tasks((_task(1, "1", max_points="3"), _task(2, "1")), _SCHEME, 3)


def test_extra_task_refused() -> None:
    """A row the scheme does not have is refused."""
    tasks = (
        _task(1, "1", max_points="3"),
        _task(2, "1"),
        _task(3, "1", max_points="2"),
        _task(4, "1", max_points="1"),
    )
    with pytest.raises(VerdictRejectedError, match=r"extra tasks: \[4\]"):
        check_tasks(tasks, _SCHEME, 3)


def test_duplicate_task_refused() -> None:
    """The same task twice is refused."""
    tasks = (
        _task(1, "1", max_points="3"),
        _task(2, "1"),
        _task(2, "1"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match=r"duplicate tasks: \[2\]"):
        check_tasks(tasks, _SCHEME, 3)


def test_points_above_max_refused() -> None:
    """Points above the task maximum are refused."""
    tasks = (
        _task(1, "1", max_points="3"),
        _task(2, "6"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 2: points 6 above max 5"):
        check_tasks(tasks, _SCHEME, 3)


def test_three_decimals_refused() -> None:
    """Points with a third decimal are refused."""
    tasks = (
        _task(1, "1", max_points="3"),
        _task(2, "2.555"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 2: more than 2 decimals"):
        check_tasks(tasks, _SCHEME, 3)


def test_manipulation_needs_zero() -> None:
    """A manipulation is 0 points."""
    tasks = (
        _task(1, "1", max_points="3"),
        _task(2, "1", manipulation=True),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 2: manipulation scores 0"):
        check_tasks(tasks, _SCHEME, 3)


def test_empty_explanation_refused() -> None:
    """An explanation of only spaces is empty."""
    tasks = (
        _task(1, "1", max_points="3", explanation="   "),
        _task(2, "1"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 1: explanation is empty"):
        check_tasks(tasks, _SCHEME, 3)


def test_long_explanation_refused() -> None:
    """An explanation longer than 1500 characters is refused."""
    tasks = (
        _task(1, "1", max_points="3", explanation="а" * 1501),
        _task(2, "1"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 1: explanation is too long"):
        check_tasks(tasks, _SCHEME, 3)


def test_page_out_of_range_refused() -> None:
    """A page number past the work is refused."""
    tasks = (
        _task(1, "1", max_points="3", pages=(4,)),
        _task(2, "1"),
        _task(3, "1", max_points="2"),
    )
    with pytest.raises(VerdictRejectedError, match="task 1: page 4"):
        check_tasks(tasks, _SCHEME, 3)


def test_pages_seen_must_cover_every_page() -> None:
    """Every page is seen once; order and duplicates do not matter."""
    with pytest.raises(VerdictRejectedError, match="pages seen"):
        check_pages_seen((1, 2), 3)
    check_pages_seen((3, 1, 2, 2), 3)


def test_flag_makes_manual() -> None:
    """One unreadable or unsure task waits for the teacher."""
    assert status_for((_task(1, "0", unreadable=True),)) is VerdictStatus.MANUAL
    assert status_for((_task(1, "0", unsure=True),)) is VerdictStatus.MANUAL


def test_clean_is_published() -> None:
    """A verdict with no flags is published."""
    assert status_for((_task(1, "1"),)) is VerdictStatus.PUBLISHED


def test_appeal_window_is_seven_days() -> None:
    """An appeal is open until the same moment seven days later."""
    published = datetime(2026, 10, 18, 12, tzinfo=UTC)
    assert appeal_open_until(published) == published + timedelta(days=7)
