"""Before any handler: private chats only, a rate limit, who is a teacher."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any, cast, final, override

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode

from smr.bot.states import ConsentSG
from smr.roster.application.use_cases import Memberships
from smr.roster.domain import CONSENT_VERSION, BindingStatus

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


def _is_admin_command(event: TelegramObject) -> bool:
    text = event.text if isinstance(event, Message) else None
    return bool(text) and text.startswith("/admin")


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


@final
class ConsentMiddleware(BaseMiddleware):
    """A bound student with an old notice sees it again before anything else."""

    @override
    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Open the notice when the accepted version is not the current one.

        Args:
            handler: Handler - The next step.
            event: TelegramObject - A message or a button press.
            data: dict[str, Any] - The middleware data.

        Returns:
            Any - The handler's result, or None when the notice took over.

        """
        if data.get("is_admin") or _is_admin_command(event):
            return await handler(event, data)
        manager = data.get("dialog_manager")
        container = data.get("dishka_container")
        user_id = _user_id(event)
        if manager is None or container is None or user_id is None:
            return await handler(event, data)
        dialog = cast("DialogManager", manager)
        if dialog.has_context() and dialog.current_context().state.group == ConsentSG:
            return await handler(event, data)
        memberships = await container.get(Memberships)
        rows = await memberships(user_id)
        stale = any(
            row.student.binding is BindingStatus.BOUND
            and row.student.consent_version != CONSENT_VERSION
            for row in rows
        )
        if not stale:
            return await handler(event, data)
        await dialog.start(ConsentSG.renew, mode=StartMode.RESET_STACK)
        return None
