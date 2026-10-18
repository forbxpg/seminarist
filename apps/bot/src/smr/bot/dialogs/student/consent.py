"""The current privacy notice, when a bound student has not accepted it yet."""

from __future__ import annotations

from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, StartMode, Window
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import actor
from smr.bot.states import ConsentSG, StudentSG
from smr.bot.texts import CONSENT
from smr.roster.application.use_cases import AcceptConsent, Memberships
from smr.roster.domain import BindingStatus


async def _text_getter(**_: object) -> dict[str, object]:
    return {"consent": CONSENT}


@inject
async def _accept(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    accept: FromDishka[AcceptConsent],
    memberships: FromDishka[Memberships],
) -> None:
    _ = await accept(actor(manager))
    rows = [
        row
        for row in await memberships(actor(manager))
        if row.student.binding is BindingStatus.BOUND
    ]
    _ = await callback.answer("Согласие принято.")
    if len(rows) == 1:
        await manager.start(
            StudentSG.menu,
            data={"group_id": str(rows[0].group.group_id)},
            mode=StartMode.RESET_STACK,
        )
        return
    await manager.start(StudentSG.groups, mode=StartMode.RESET_STACK)


consent_dialog = Dialog(
    Window(
        Format("{consent}"),
        Button(Const("Принимаю"), id="accept", on_click=_accept),
        getter=_text_getter,
        state=ConsentSG.renew,
    ),
)
