"""A student's БДЗ: the statement, the PDF, the breakdown and the appeal."""

from __future__ import annotations

import uuid
from operator import itemgetter
from typing import Any

from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bdz.application.use_cases import (
    BdzStatement,
    SendBdz,
    StudentBdz,
    StudentBdzList,
    Upload,
)
from smr.bdz.domain import BdzSubmission
from smr.bot.dialogs.common import actor, remembered_id
from smr.bot.files import receive
from smr.bot.states import StudentSG
from smr.bot.texts import moment, points, safe
from smr.bot.verdicts import verdict_messages
from smr.review.application.use_cases import FileAppeal, MyVerdict
from smr.review.domain import VerdictStatus

_MIDDLEWARE = Any
_PHOTO = (
    "Пришлите БДЗ одним PDF-файлом. Как собрать фото в PDF: iPhone — «Файлы» → "
    "«Сканировать документы»; Android — Google Диск → «Сканировать»."
)


def _bdz(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "bdz_id")


def _status(row: StudentBdz) -> str:
    if row.submission is None:
        return "не сдано"
    if row.status is VerdictStatus.PUBLISHED and row.total is not None:
        return f"🤖 {points(row.total)} из {points(row.bdz.max_points)}"
    if row.status is VerdictStatus.MANUAL:
        return "у преподавателя"
    if row.status is VerdictStatus.APPEALED:
        return "апелляция рассматривается"
    if row.status is VerdictStatus.FINAL and row.total is not None:
        return f"✅ {points(row.total)} из {points(row.bdz.max_points)}"
    return "ждёт проверки"


def _line(row: StudentBdz) -> str:
    due = moment(row.bdz.deadline)
    return f"{row.bdz.title} · {due} · {_status(row)}"


@inject
async def _list_getter(
    dialog_manager: DialogManager,
    listing: FromDishka[StudentBdzList],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    group_id = remembered_id(dialog_manager, "group_id")
    rows = await listing(actor(dialog_manager), group_id)
    return {
        "empty": not rows,
        "items": [(_line(row), str(row.bdz.bdz_id)) for row in rows],
    }


async def _picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["bdz_id"] = item_id
    await manager.switch_to(StudentSG.bdz)


@inject
async def _card_getter(
    dialog_manager: DialogManager,
    listing: FromDishka[StudentBdzList],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    bdz_id = _bdz(dialog_manager)
    group_id = remembered_id(dialog_manager, "group_id")
    rows = await listing(actor(dialog_manager), group_id)
    row = next(item for item in rows if item.bdz.bdz_id == bdz_id)
    scheme = ", ".join(
        f"{task.number}: {points(task.max_points)}" for task in row.tasks
    )
    return {
        "text": (
            f"<b>{safe(row.bdz.title)}</b>\n"
            f"Срок: {moment(row.bdz.deadline)}\n"
            f"Задачи: {scheme}\n"
            f"{_status(row)}"
        ),
        "can_send": row.status is not VerdictStatus.APPEALED,
        "send_label": (
            "📤 Прислать новую версию" if row.submission is not None else "📤 Сдать PDF"
        ),
        "has_verdict": row.status in {VerdictStatus.PUBLISHED, VerdictStatus.FINAL},
    }


@inject
async def _statement(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    statement: FromDishka[BdzStatement],
) -> None:
    file_id, title = await statement(actor(manager), _bdz(manager))
    if callback.message is not None:
        _ = await callback.message.answer_document(file_id, caption=safe(title))
    manager.show_mode = ShowMode.SEND


@inject
async def _upload(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    send: FromDishka[SendBdz],
) -> None:
    document = message.document
    name = "" if document is None or document.file_name is None else document.file_name
    mime = "" if document is None or document.mime_type is None else document.mime_type
    pdf = mime == "application/pdf" or name.lower().endswith(".pdf")
    if message.photo or not pdf:
        _ = await message.answer(_PHOTO)
        return
    if message.bot is None:
        return
    got = await receive(message.bot, message)
    if got is None or message.document is None:
        _ = await message.answer(_PHOTO)
        return
    saved: BdzSubmission = await send(
        actor(manager),
        _bdz(manager),
        Upload(got.data, got.tg_file_id, got.tg_file_unique_id, got.sent_at),
    )
    _ = await message.answer(
        f"Принято, версия {saved.version}. Проверка — после запуска преподавателем.",
    )
    await manager.switch_to(StudentSG.bdz)


@inject
async def _verdict(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    mine: FromDishka[MyVerdict],
    listing: FromDishka[StudentBdzList],
) -> None:
    bdz_id = _bdz(manager)
    rows = await listing(actor(manager), remembered_id(manager, "group_id"))
    row = next(item for item in rows if item.bdz.bdz_id == bdz_id)
    if row.submission is None:
        return
    view = await mine(actor(manager), "bdz", row.submission.submission_id)
    if view is None or callback.message is None:
        return
    messages = verdict_messages(view, title=row.bdz.title)
    _ = await callback.message.answer(messages[0])
    for text in messages[1:]:
        _ = await callback.message.answer(text)
    manager.show_mode = ShowMode.SEND
    if view.can_appeal and view.appeal_until is not None:
        manager.dialog_data["appeal_until"] = moment(view.appeal_until)
        await manager.switch_to(StudentSG.bdz_verdict)


@inject
async def _verdict_getter(
    dialog_manager: DialogManager,
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    return {"until": dialog_manager.dialog_data.get("appeal_until", "")}


async def _appeal_text(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
) -> None:
    manager.dialog_data["appeal"] = " ".join(text.split())
    await manager.switch_to(StudentSG.bdz_appeal_confirm)


@inject
async def _confirm_appeal(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    appeal: FromDishka[FileAppeal],
    listing: FromDishka[StudentBdzList],
) -> None:
    rows = await listing(actor(manager), remembered_id(manager, "group_id"))
    row = next(item for item in rows if item.bdz.bdz_id == _bdz(manager))
    if row.submission is None:
        return
    _ = await appeal(
        actor(manager),
        "bdz",
        row.submission.submission_id,
        str(manager.dialog_data["appeal"]),
    )
    _ = await callback.answer("Апелляция отправлена преподавателю.", show_alert=True)
    await manager.switch_to(StudentSG.bdz)


def student_bdz_windows() -> list[Window]:
    """The БДЗ windows of the student menu.

    Returns:
        list[Window] - The list, the card, the upload, the breakdown and the appeal.

    """
    return [
        Window(
            Const("БДЗ:"),
            Const("Пока ничего не задано.", when="empty"),
            ScrollingGroup(
                Select(
                    Format("{item[0]}"),
                    id="bdz",
                    item_id_getter=itemgetter(1),
                    items="items",
                    on_click=_picked,
                ),
                id="bdzs",
                width=1,
                height=6,
            ),
            SwitchTo(Const("« Меню"), id="back", state=StudentSG.menu),
            getter=_list_getter,
            state=StudentSG.bdz_list,
        ),
        Window(
            Format("{text}"),
            Button(Const("📄 Условие"), id="statement", on_click=_statement),
            SwitchTo(
                Format("{send_label}"),
                id="send",
                state=StudentSG.bdz_upload,
                when="can_send",
            ),
            Button(
                Const("🧾 Разбор"),
                id="verdict",
                on_click=_verdict,
                when="has_verdict",
            ),
            SwitchTo(Const("« БДЗ"), id="back", state=StudentSG.bdz_list),
            getter=_card_getter,
            state=StudentSG.bdz,
        ),
        Window(
            Const("Пришлите один PDF-файл."),
            MessageInput(
                _upload,
                content_types=[ContentType.DOCUMENT, ContentType.PHOTO],
            ),
            SwitchTo(Const("« Назад"), id="back", state=StudentSG.bdz),
            state=StudentSG.bdz_upload,
        ),
        Window(
            Format("Разбор отправлен выше. Апелляцию можно подать до {until}."),
            SwitchTo(Const("⚖️ Апелляция"), id="appeal", state=StudentSG.bdz_appeal),
            SwitchTo(Const("« БДЗ"), id="back", state=StudentSG.bdz),
            getter=_verdict_getter,
            state=StudentSG.bdz_verdict,
        ),
        Window(
            Format(
                "Апелляцию проверит преподаватель. Оценка может как вырасти, "
                "так и снизиться. Подать можно один раз, до {until}.\n"
                "Напишите, с чем не согласны.",
            ),
            TextInput(id="appeal", on_success=_appeal_text),
            SwitchTo(Const("Отмена"), id="cancel", state=StudentSG.bdz),
            getter=_verdict_getter,
            state=StudentSG.bdz_appeal,
        ),
        Window(
            Const("Отправить апелляцию?"),
            Button(Const("Отправить"), id="yes", on_click=_confirm_appeal),
            SwitchTo(Const("Отмена"), id="no", state=StudentSG.bdz),
            state=StudentSG.bdz_appeal_confirm,
        ),
    ]
