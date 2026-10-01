"""Small pieces every dialog uses."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from aiogram.fsm.state import State
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

type OnClick = Callable[[CallbackQuery, object, DialogManager], Awaitable[None]]


def go(state: State) -> OnClick:
    """Make a button handler that switches the dialog to a state.

    Args:
        state: State - Where to go.

    Returns:
        OnClick - The handler.

    """

    async def handler(
        _callback: CallbackQuery,
        _button: object,
        manager: DialogManager,
    ) -> None:
        await manager.switch_to(state)

    return handler


def start_value(manager: DialogManager, key: str) -> str:
    """Read a value the dialog was started with.

    Args:
        manager: DialogManager - The dialog.
        key: str - The value's name.

    Returns:
        str - The value as text.

    Raises:
        KeyError: If the dialog was started without it.

    """
    data = manager.start_data
    if not isinstance(data, dict) or key not in data:
        raise KeyError(key)
    return str(data[key])


def remembered_id(manager: DialogManager, key: str) -> uuid.UUID:
    """Read an id the dialog remembered, or was started with.

    Args:
        manager: DialogManager - The dialog.
        key: str - The id's name.

    Returns:
        uuid.UUID - The id; a `KeyError` when the dialog knows no such id.

    """
    value = manager.dialog_data.get(key)
    if value is None:
        value = start_value(manager, key)
    return uuid.UUID(str(value))


def actor(manager: DialogManager) -> int:
    """Tell who acts in this dialog.

    Args:
        manager: DialogManager - The dialog.

    Returns:
        int - The Telegram user id.

    Raises:
        LookupError: If the event has no user.

    """
    user = getattr(manager.event, "from_user", None)
    if user is None:
        msg = "the event has no user"
        raise LookupError(msg)
    user_id: int = user.id
    return user_id


def start_with(state: State, *keys: str) -> OnClick:
    """Make a button handler that starts another dialog with this one's ids.

    Args:
        state: State - The other dialog's first state.
        *keys: str - The ids to pass, read from this dialog.

    Returns:
        OnClick - The handler.

    """

    async def handler(
        _callback: CallbackQuery,
        _button: object,
        manager: DialogManager,
    ) -> None:
        data = {key: str(remembered_id(manager, key)) for key in keys}
        await manager.start(state, data=data)

    return handler
