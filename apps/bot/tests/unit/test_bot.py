"""The bot's pure pieces and its wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, User

from smr.bot._app import build_dispatcher
from smr.bot.di import make_container
from smr.bot.exports import cell
from smr.bot.handlers.start import start
from smr.bot.middlewares import GateMiddleware
from smr.bot.parsing import parse_moment, parse_points
from smr.bot.states import AdminSG
from smr.bot.texts import moment, points, safe
from smr.core.access import AdminGuard
from smr.core.clock import MOSCOW

# 2 October 2026, 12:00 in Moscow.
_NOW = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("07.10", datetime(2026, 10, 7, 23, 59, tzinfo=MOSCOW)),
        ("7.10 18:30", datetime(2026, 10, 7, 18, 30, tzinfo=MOSCOW)),
        (" 07.10 9.05 ", datetime(2026, 10, 7, 9, 5, tzinfo=MOSCOW)),
        ("07.10.27", datetime(2027, 10, 7, 23, 59, tzinfo=MOSCOW)),
        ("07.10.2026 08:00", datetime(2026, 10, 7, 8, 0, tzinfo=MOSCOW)),
        # A date long past this year means next year: a February deadline set in autumn.
        ("15.02", datetime(2027, 2, 15, 23, 59, tzinfo=MOSCOW)),
        # A recent past date stays: the teacher records yesterday's seminar.
        ("01.10 10:00", datetime(2026, 10, 1, 10, 0, tzinfo=MOSCOW)),
    ],
)
def test_moments_are_read_as_moscow_time(text: str, expected: datetime) -> None:
    """Every accepted way of typing a date lands on the intended moment."""
    assert parse_moment(text, _NOW) == expected


@pytest.mark.parametrize(
    "text",
    ["", "завтра", "31.02", "07.13", "07.10 25:00", "7/10"],
)
def test_nonsense_is_not_a_moment(text: str) -> None:
    """A wrong date is refused with ValueError, which the dialogs turn into a hint."""
    with pytest.raises(ValueError, match=r"."):
        _ = parse_moment(text, _NOW)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2", Decimal(2)), ("2.5", Decimal("2.5")), ("2,25", Decimal("2.25")), ("0", 0)],
)
def test_points_are_read(text: str, expected: Decimal) -> None:
    """Points accept a comma or a dot."""
    assert parse_points(text) == expected


@pytest.mark.parametrize("text", ["-1", "2.555", "abc", "NaN", "Infinity", ""])
def test_wrong_points_are_refused(text: str) -> None:
    """Negative, too precise or non-numeric points are refused."""
    with pytest.raises(ValueError, match=r"."):
        _ = parse_points(text)


def test_texts_are_written_for_people() -> None:
    """Moments show in Moscow time, points without trailing zeros, HTML is escaped."""
    assert moment(_NOW) == "02.10 12:00"
    assert points(Decimal("2.50")) == "2.5"
    assert points(Decimal("3.00")) == "3"
    assert points(Decimal(10)) == "10"
    assert safe("<b>Иванов & Ко</b>") == "&lt;b&gt;Иванов &amp; Ко&lt;/b&gt;"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('=HYPERLINK("x")', '\'=HYPERLINK("x")'),
        ("+1", "'+1"),
        ("-1", "'-1"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("Иванов Иван", "Иванов Иван"),
        (Decimal("2.5"), Decimal("2.5")),
        (3, 3),
    ],
)
def test_sheet_cells_never_hold_formulas(value: object, expected: object) -> None:
    """A name that starts like a formula is written as text."""
    assert cell(value) == expected


def _message(chat_type: str, user_id: int = 7) -> Message:
    return Message(
        message_id=1,
        date=_NOW,
        chat=Chat(id=user_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="x"),
        text="hi",
    )


async def test_the_gate_lets_private_chats_through_and_marks_teachers() -> None:
    """A teacher's private message passes with is_admin; a group chat is dropped."""
    gate = GateMiddleware(AdminGuard([7]))
    seen: list[object] = []

    async def handler(_event: object, data: dict[str, object]) -> str:
        seen.append(data["is_admin"])
        return "ok"

    assert await gate(handler, _message("private"), {}) == "ok"
    assert await gate(handler, _message("group"), {}) is None
    assert await gate(handler, _message("private", user_id=8), {}) == "ok"
    assert seen == [True, False]


async def test_the_gate_throttles_a_flood() -> None:
    """Past the limit within the window, events are dropped."""
    gate = GateMiddleware(AdminGuard([]), limit=3, window_seconds=60)

    async def handler(_event: object, _data: dict[str, object]) -> str:
        return "ok"

    results = [await gate(handler, _message("private"), {}) for _ in range(5)]
    assert results == ["ok", "ok", "ok", None, None]


def test_the_container_is_complete() -> None:
    """Every handler's dependencies can be built: the graph validates without a database."""
    assert make_container() is not None


async def test_the_dispatcher_assembles() -> None:
    """Routers, dialogs and DI fit together: no duplicate states or broken windows."""
    container = make_container()
    try:
        dispatcher = build_dispatcher(container, MemoryStorage(), AdminGuard([1]))
        assert dispatcher.sub_routers
    finally:
        await container.close()


class _Manager:
    def __init__(self) -> None:
        self.started: list[object] = []

    async def start(self, state: object, **_: object) -> None:
        self.started.append(state)


async def test_start_opens_the_teachers_menu_for_a_teacher() -> None:
    """A teacher with no student binding gets the teacher's menu, not the invite hint."""
    manager = _Manager()

    async def no_memberships(_user_id: int) -> list[object]:
        return []

    await start(
        _message("private"),
        manager,
        no_memberships,
        is_admin=True,
    )
    assert manager.started == [AdminSG.menu]
