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


def test_homework_published_names_the_work_and_the_breakdown() -> None:
    """Ordinary homework uses its own label and the one-task explanation."""
    assert render(
        NotificationKind.REVIEW_PUBLISHED,
        {
            "title": "ДЗ 3",
            "total": "2",
            "max": "3",
            "appeal_until": _DEADLINE,
            "label": "домашнее задание",
            "breakdown": "Верно.",
        },
    ) == (
        "🤖 Ваше домашнее задание <b>ДЗ 3</b> проверил ИИ-ассистент: 2 из 3. "
        "Верно. Не согласны — подайте апелляцию до 07.10 23:59; "
        "её проверит преподаватель."
    )


def test_homework_manual_names_the_work() -> None:
    """A file the agent cannot read is still called homework, not a БДЗ."""
    text = render(
        NotificationKind.REVIEW_MANUAL,
        {"title": "ДЗ 3", "pages": [1], "label": "домашнее задание"},
    )
    assert "Ваше домашнее задание <b>ДЗ 3</b>" in text
    assert "БДЗ" not in text


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
