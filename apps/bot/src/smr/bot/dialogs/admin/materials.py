"""Seminar cards: create "Семинар 4", attach its files, publish with a notice."""

from __future__ import annotations

import uuid
from operator import itemgetter
from typing import Any

from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Cancel,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import actor, go, remembered_id
from smr.bot.files import receive, send_file
from smr.bot.states import MaterialsSG
from smr.bot.texts import safe
from smr.materials.application.use_cases import (
    AddMaterialFile,
    CreateMaterial,
    DeleteMaterial,
    ListMaterials,
    MaterialUpload,
    PublishMaterial,
    UnpublishMaterial,
)
from smr.materials.domain import EmptyMaterialError, MaterialStatus

_MIDDLEWARE = Any


def _card(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "material_id")


@inject
async def _list_getter(
    dialog_manager: DialogManager,
    materials: FromDishka[ListMaterials],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    cards = await materials(
        actor(dialog_manager),
        remembered_id(dialog_manager, "group_id"),
    )
    icon = {MaterialStatus.DRAFT: "📝", MaterialStatus.PUBLISHED: "✅"}
    return {
        "cards": [
            (
                f"{icon[card.status]} {card.title} · файлов {len(files)}",
                str(card.material_id),
            )
            for card, files in cards
        ],
        "empty": not cards,
    }


async def _picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["material_id"] = item_id
    await manager.switch_to(MaterialsSG.card)


@inject
async def _create(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    create: FromDishka[CreateMaterial],
) -> None:
    if message.from_user is None:
        return
    card = await create(message.from_user.id, remembered_id(manager, "group_id"), value)
    manager.dialog_data["material_id"] = str(card.material_id)
    await manager.switch_to(MaterialsSG.upload)


@inject
async def _card_getter(
    dialog_manager: DialogManager,
    materials: FromDishka[ListMaterials],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    target = _card(dialog_manager)
    cards = await materials(
        actor(dialog_manager),
        remembered_id(dialog_manager, "group_id"),
    )
    found = next(((c, f) for c, f in cards if c.material_id == target), None)
    if found is None:
        return {"text": "Карточка удалена.", "draft": False, "published": False}
    card, files = found
    status = (
        "опубликована ✅" if card.status is MaterialStatus.PUBLISHED else "черновик 📝"
    )
    return {
        "text": f"<b>{safe(card.title)}</b>\nСтатус: {status}\nФайлов: {len(files)}",
        "draft": card.status is MaterialStatus.DRAFT,
        "published": card.status is MaterialStatus.PUBLISHED,
    }


@inject
async def _show(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    materials: FromDishka[ListMaterials],
) -> None:
    cards = await materials(callback.from_user.id, remembered_id(manager, "group_id"))
    target = _card(manager)
    for card, files in cards:
        if card.material_id == target:
            for file in files:
                await send_file(callback.message, file.tg_file_id, file.kind)
    manager.show_mode = ShowMode.SEND


@inject
async def _file_received(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    add: FromDishka[AddMaterialFile],
) -> None:
    manager.show_mode = ShowMode.DELETE_AND_SEND
    if message.bot is None or message.from_user is None:
        return
    received = await receive(message.bot, message)
    if received is None:
        _ = await message.answer("Пришлите файл: PDF, DOCX или фото.")
        return
    _ = await add(
        message.from_user.id,
        _card(manager),
        MaterialUpload(received.data, received.tg_file_id),
    )


@inject
async def _publish(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    publish: FromDishka[PublishMaterial],
) -> None:
    try:
        told = await publish(callback.from_user.id, _card(manager))
    except EmptyMaterialError:
        _ = await callback.answer("Сначала добавьте файл.", show_alert=True)
        return
    _ = await callback.answer(
        f"Опубликовано. Уведомление получат: {told}.",
        show_alert=True,
    )
    await manager.switch_to(MaterialsSG.card)


@inject
async def _unpublish(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    unpublish: FromDishka[UnpublishMaterial],
) -> None:
    await unpublish(callback.from_user.id, _card(manager))
    _ = await callback.answer("Снято с публикации.")


@inject
async def _delete(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    delete: FromDishka[DeleteMaterial],
) -> None:
    await delete(callback.from_user.id, _card(manager))
    _ = await callback.answer("Удалено.")
    await manager.switch_to(MaterialsSG.list)


materials_dialog = Dialog(
    Window(
        Const("Семинары группы (📝 черновик, ✅ опубликован):"),
        Const("Пока ничего нет.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="card",
                item_id_getter=itemgetter(1),
                items="cards",
                on_click=_picked,
            ),
            id="cards_list",
            width=1,
            height=8,
        ),
        SwitchTo(Const("➕ Новый семинар"), id="new", state=MaterialsSG.new_title),
        Cancel(Const("« Группа")),
        getter=_list_getter,
        state=MaterialsSG.list,
    ),
    Window(
        Const("Название кнопки для студентов, например «Семинар 4»:"),
        TextInput(id="title", on_success=_create),
        SwitchTo(Const("Отмена"), id="cancel", state=MaterialsSG.list),
        state=MaterialsSG.new_title,
    ),
    Window(
        Format("{text}"),
        Row(
            SwitchTo(Const("📎 Добавить файлы"), id="add", state=MaterialsSG.upload),
            Button(Const("👁 Показать"), id="show", on_click=_show),
        ),
        SwitchTo(
            Const("📣 Опубликовать"),
            id="publish",
            state=MaterialsSG.publish,
            when="draft",
        ),
        Button(
            Const("🙈 Снять с публикации"),
            id="unpublish",
            on_click=_unpublish,
            when="published",
        ),
        SwitchTo(Const("🗑 Удалить"), id="delete", state=MaterialsSG.delete),
        SwitchTo(Const("« Семинары"), id="back", state=MaterialsSG.list),
        getter=_card_getter,
        state=MaterialsSG.card,
    ),
    Window(
        Const("Пришлите PDF (или несколько файлов). Затем — «Готово»."),
        MessageInput(
            _file_received,
            content_types=[ContentType.DOCUMENT, ContentType.PHOTO],
        ),
        SwitchTo(Const("✅ Готово"), id="done", state=MaterialsSG.card),
        state=MaterialsSG.upload,
    ),
    Window(
        Const("Опубликовать и уведомить всех привязанных студентов группы?"),
        Button(Const("Да, опубликовать"), id="yes", on_click=_publish),
        Button(Const("Нет"), id="no", on_click=go(MaterialsSG.card)),
        state=MaterialsSG.publish,
    ),
    Window(
        Const("Удалить карточку и её файлы?"),
        Button(Const("Да, удалить"), id="yes", on_click=_delete),
        Button(Const("Нет"), id="no", on_click=go(MaterialsSG.card)),
        state=MaterialsSG.delete,
    ),
)
