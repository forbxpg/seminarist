"""The texts of БДЗ, reviews and appeals."""

from __future__ import annotations

from smr.notifications.domain import NotificationKind, render

_DEADLINE = "2026-10-07T20:59:00+00:00"


def test_bdz_published() -> None:
    """A new БДЗ tells the title and the Moscow deadline."""
    assert render(
        NotificationKind.BDZ_PUBLISHED,
        {"title": "Контрольная", "deadline": _DEADLINE, "group": "К01"},
    ) == (
        "📘 Новое БДЗ: <b>Контрольная</b>. Срок: 07.10 23:59 (МСК). Условие — в «БДЗ»."
    )


def test_review_published() -> None:
    """A clean verdict tells the score and the appeal deadline."""
    assert render(
        NotificationKind.REVIEW_PUBLISHED,
        {
            "title": "Контрольная",
            "total": "7",
            "max": "10",
            "appeal_until": _DEADLINE,
        },
    ) == (
        "🤖 Ваше БДЗ <b>Контрольная</b> проверил ИИ-ассистент: 7 из 10. "
        "Разбор по задачам — в «БДЗ». Не согласны — подайте апелляцию до 07.10 23:59; "
        "её проверит преподаватель."
    )


def test_review_manual_with_pages() -> None:
    """Unreadable pages are named, and a better scan is still offered."""
    assert render(
        NotificationKind.REVIEW_MANUAL,
        {"title": "Контрольная", "pages": [4, 7]},
    ) == (
        "🧑‍🏫 Ваше БДЗ <b>Контрольная</b> передано преподавателю на ручную проверку. "
        "Не удалось прочитать страницы: 4, 7. До дедлайна можно прислать скан получше."
    )


def test_manual_without_pages_keeps_the_resubmit_line() -> None:
    """An unsure but readable work still offers a better scan."""
    text = render(NotificationKind.REVIEW_MANUAL, {"title": "Контрольная", "pages": []})
    assert "страницы" not in text
    assert text.endswith("До дедлайна можно прислать скан получше.")


def test_review_final_with_before() -> None:
    """A teacher's grade names what it was."""
    assert render(
        NotificationKind.REVIEW_FINAL,
        {"title": "Контрольная", "total": "5", "max": "10", "before": "7"},
    ) == (
        "✅ Преподаватель проверил БДЗ <b>Контрольная</b>: 5 из 10 (было 7). "
        "Это окончательная оценка."
    )


def test_final_without_before_has_no_was() -> None:
    """A first teacher grade has no previous total."""
    text = render(
        NotificationKind.REVIEW_FINAL,
        {"title": "Контрольная", "total": "5", "max": "10"},
    )
    assert "было" not in text
    assert "5 из 10." in text


def test_appeal_filed() -> None:
    """An appeal tells the teachers which work, without a name."""
    assert render(
        NotificationKind.APPEAL_FILED,
        {"title": "Контрольная", "work_no": "abcd1234"},
    ) == (
        "⚖️ Апелляция по БДЗ <b>Контрольная</b> (работа №abcd1234). "
        "Откройте «Ручная проверка» в /admin."
    )


def test_titles_are_escaped() -> None:
    """A title cannot inject markup."""
    text = render(
        NotificationKind.BDZ_PUBLISHED,
        {"title": "<x>", "deadline": _DEADLINE, "group": "К01"},
    )
    assert "&lt;x&gt;" in text
