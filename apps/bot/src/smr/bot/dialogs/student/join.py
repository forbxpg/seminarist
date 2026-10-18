"""Joining a group by its link: consent, pick a name, wait for the teacher."""

from __future__ import annotations

import logging
import uuid
from operator import itemgetter
from typing import Any

from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Cancel, Row, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import go, start_value
from smr.bot.states import JoinSG
from smr.bot.texts import CONSENT, safe
from smr.core.access import AdminGuard
from smr.roster.application.contracts import RosterApi
from smr.roster.application.use_cases import (
    ClaimableNames,
    ClaimStudent,
    Membership,
    ResolveInvite,
)
from smr.roster.domain import (
    CONSENT_VERSION,
    AlreadyBoundError,
    NameTakenError,
)

logger = logging.getLogger(__name__)


def _invite(manager: DialogManager) -> str:
    return start_value(manager, "invite")


@inject
async def _consent_getter(
    dialog_manager: DialogManager,
    resolve: FromDishka[ResolveInvite],
    **_: Any,  # ruff: ignore[any-type] -- aiogram-dialog passes the middleware data
) -> dict[str, object]:
    group = await resolve(_invite(dialog_manager))
    return {"group": safe(group.name), "consent": CONSENT}


@inject
async def _names_getter(
    dialog_manager: DialogManager,
    names: FromDishka[ClaimableNames],
    **_: Any,  # ruff: ignore[any-type] -- aiogram-dialog passes the middleware data
) -> dict[str, object]:
    free = await names(_invite(dialog_manager))
    return {
        "names": [(student.full_name, str(student.student_id)) for student in free],
        "empty": not free,
    }


async def _picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["student_id"] = item_id
    await manager.switch_to(JoinSG.confirm)


@inject
async def _confirm_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **_: Any,  # ruff: ignore[any-type] -- aiogram-dialog passes the middleware data
) -> dict[str, object]:
    student = await roster.student(
        uuid.UUID(str(dialog_manager.dialog_data["student_id"])),
    )
    return {"name": safe("" if student is None else student.full_name)}


@inject
async def _confirmed(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    claim: FromDishka[ClaimStudent],
    guard: FromDishka[AdminGuard],
) -> None:
    student_id = uuid.UUID(str(manager.dialog_data["student_id"]))
    try:
        membership = await claim(
            _invite(manager),
            student_id,
            callback.from_user.id,
            CONSENT_VERSION,
        )
    except NameTakenError:
        _ = await callback.answer(
            "Эту фамилию уже выбрали. Выберите свою.",
            show_alert=True,
        )
        await manager.switch_to(JoinSG.pick)
        return
    except AlreadyBoundError:
        _ = await callback.answer(
            "Вы уже выбрали фамилию в этой группе. Дождитесь преподавателя.",
            show_alert=True,
        )
        await manager.switch_to(JoinSG.waiting)
        return
    await _tell_teachers(callback, guard, membership)
    await manager.switch_to(JoinSG.waiting)


async def _tell_teachers(
    callback: CallbackQuery,
    guard: AdminGuard,
    membership: Membership,
) -> None:
    """Push the request to every teacher with buttons to decide at once."""
    bot = callback.bot
    if bot is None:
        return
    student = membership.student
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Это он(а)",
                    callback_data=f"bind:approve:{student.student_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"bind:reject:{student.student_id}",
                ),
            ],
        ],
    )
    text = (
        f"🙋 Заявка в группе {safe(membership.group.title)}: "
        f"<b>{safe(student.full_name)}</b>"
    )
    for admin in sorted(guard.admin_ids):
        try:
            _ = await bot.send_message(admin, text, reply_markup=keyboard)
        except TelegramAPIError:
            logger.warning("could not tell a teacher about a binding request")


join_dialog = Dialog(
    Window(
        Format("Группа: <b>{group}</b>\n\n{consent}"),
        Row(
            Button(Const("✅ Согласен"), id="agree", on_click=go(JoinSG.pick)),
            Cancel(Const("Отмена")),
        ),
        getter=_consent_getter,
        state=JoinSG.consent,
    ),
    Window(
        Const("Выберите себя в списке группы:"),
        Const("Свободных фамилий нет. Напишите преподавателю.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="name",
                item_id_getter=itemgetter(1),
                items="names",
                on_click=_picked,
            ),
            id="names",
            width=1,
            height=8,
        ),
        Cancel(Const("Отмена")),
        getter=_names_getter,
        state=JoinSG.pick,
    ),
    Window(
        Format(
            "Вы — <b>{name}</b>?\nПосле подтверждения преподавателем откроется доступ.",
        ),
        Button(Const("Да, это я"), id="yes", on_click=_confirmed),
        Button(Const("Нет, выбрать другую"), id="no", on_click=go(JoinSG.pick)),
        getter=_confirm_getter,
        state=JoinSG.confirm,
    ),
    Window(
        Const(
            "⏳ Заявка отправлена. Как только преподаватель подтвердит, "
            "придёт сообщение, и меню откроется по /start.",
        ),
        state=JoinSG.waiting,
    ),
)
