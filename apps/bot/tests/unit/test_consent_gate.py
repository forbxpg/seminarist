"""The consent gate: a student with an old notice sees it, others pass cheaply."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from aiogram.types import Chat, Message, User

from smr.bot.middlewares import ConsentMiddleware
from smr.bot.states import ConsentSG
from smr.roster.domain import CONSENT_VERSION, BindingStatus


class _Dialog:
    def __init__(self) -> None:
        self.started: list[object] = []

    def has_context(self) -> bool:
        return False

    async def start(self, state: object, **_: object) -> None:
        self.started.append(state)


class _Container:
    def __init__(self, version: str) -> None:
        self.version: str = version
        self.queries: int = 0

    async def get(self, _kind: object) -> object:
        return self._memberships

    async def _memberships(self, _user_id: int) -> list[object]:
        self.queries += 1
        row = SimpleNamespace(binding=BindingStatus.BOUND, consent_version=self.version)
        return [SimpleNamespace(student=row)]


def _message(user_id: int = 7) -> Message:
    return Message(
        message_id=1,
        date=datetime(2026, 10, 19, tzinfo=UTC),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="x"),
        text="hi",
    )


async def _handler(_event: object, _data: dict[str, object]) -> str:
    return "ok"


async def test_current_consent_is_checked_once() -> None:
    """After one check that every row is current, the roster is not asked again."""
    gate = ConsentMiddleware()
    container = _Container(CONSENT_VERSION)
    for _ in range(3):
        data: dict[str, object] = {
            "dialog_manager": _Dialog(),
            "dishka_container": container,
        }
        assert await gate(_handler, _message(), data) == "ok"
    assert container.queries == 1


async def test_old_consent_opens_the_notice_every_time() -> None:
    """A stale student is never remembered: each event opens the notice."""
    gate = ConsentMiddleware()
    container = _Container("v1")
    dialogs = [_Dialog(), _Dialog()]
    for dialog in dialogs:
        data: dict[str, object] = {
            "dialog_manager": dialog,
            "dishka_container": container,
        }
        assert await gate(_handler, _message(), data) is None
    assert [dialog.started for dialog in dialogs] == [
        [ConsentSG.renew],
        [ConsentSG.renew],
    ]
    assert container.queries == 2
