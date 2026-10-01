"""Before any handler: private chats only, a rate limit, who is a teacher."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any, final, override

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiogram.types import TelegramObject

    from smr.core.access import AdminGuard

type Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


def _chat_type(event: TelegramObject) -> str | None:
    if isinstance(event, Message):
        return event.chat.type
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat.type
    return None


def _user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    return None if user is None else int(user.id)


@final
class GateMiddleware(BaseMiddleware):
    """Drops what is not from a private chat, throttles, tells teachers apart."""

    def __init__(
        self,
        guard: AdminGuard,
        *,
        limit: int = 30,
        window_seconds: float = 10.0,
    ) -> None:
        self._guard: AdminGuard = guard
        self._limit: int = limit
        self._window: float = window_seconds
        self._recent: defaultdict[int, deque[float]] = defaultdict(deque)

    @override
    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Let the event through, or not.

        Args:
            handler: Handler - The next step.
            event: TelegramObject - A message or a button press.
            data: dict[str, Any] - The middleware data.

        Returns:
            Any - The handler's result, or None when the event is dropped.

        """
        user_id = _user_id(event)
        if user_id is None or _chat_type(event) != ChatType.PRIVATE:
            return None
        if self._too_fast(user_id):
            return None
        data["is_admin"] = self._guard.is_admin(user_id)
        return await handler(event, data)

    def _too_fast(self, user_id: int) -> bool:
        now = time.monotonic()
        recent = self._recent[user_id]
        while recent and now - recent[0] > self._window:
            _ = recent.popleft()
        if len(recent) >= self._limit:
            return True
        recent.append(now)
        return False
