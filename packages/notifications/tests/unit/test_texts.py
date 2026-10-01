"""The texts of notices."""

from __future__ import annotations

from smr.notifications.domain import NotificationKind, render


def test_values_are_escaped() -> None:
    """A title with HTML in it cannot inject markup."""
    text = render(
        NotificationKind.MATERIAL_PUBLISHED,
        {"title": "<b>x</b>", "group": "К01"},
    )
    assert "&lt;b&gt;x&lt;/b&gt;" in text


def test_deadline_is_told_in_moscow_time() -> None:
    """A UTC deadline reads as Moscow time."""
    text = render(
        NotificationKind.DEADLINE_REMINDER,
        {"title": "ДЗ 3", "deadline": "2026-10-07T20:59:00+00:00"},
    )
    assert "07.10 23:59" in text


def test_grade_without_comment() -> None:
    """A grade without a comment has no comment line."""
    text = render(
        NotificationKind.HOMEWORK_GRADED,
        {"title": "ДЗ 3", "points": "2.5", "max_points": "3", "comment": None},
    )
    assert "2.5 из 3" in text
    assert "Комментарий" not in text
