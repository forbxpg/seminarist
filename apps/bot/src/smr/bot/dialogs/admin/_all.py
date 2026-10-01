"""Every teacher dialog, in one list for the dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .gradebook import gradebook_dialog
from .groups import groups_dialog
from .homework import homework_dialog
from .materials import materials_dialog
from .sessions import sessions_dialog

if TYPE_CHECKING:
    from aiogram_dialog import Dialog


def admin_dialogs() -> list[Dialog]:
    """List the teacher's dialogs.

    Returns:
        list[Dialog] - Every one of them.

    """
    return [
        groups_dialog,
        sessions_dialog,
        homework_dialog,
        materials_dialog,
        gradebook_dialog,
    ]
