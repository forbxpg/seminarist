"""The teacher publishes a БДЗ and looks at who sent it."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from operator import itemgetter
from typing import Any

from aiogram import Bot
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bdz.application.use_cases import (
    BdzDraft,
    BdzRoster,
    CreateBdz,
    DeleteBdz,
    ExportBdz,
    ListBdz,
    UpdateBdzDeadline,
    Upload,
)
from smr.bdz.domain import parse_scheme
from smr.bot.dialogs.common import actor, remembered_id
from smr.bot.parsing import parse_moment
from smr.bot.states import BdzSG
from smr.bot.texts import moment, points, safe
from smr.core.clock import Clock
from smr.gradebook.application.use_cases import ListWorkTypes
from smr.gradebook.domain import ScoringMode
from smr.review.domain import VerdictStatus

_MIDDLEWARE = Any
_PDF = "Нужен один PDF-файл."


def _group(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "group_id")


def _bdz(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "bdz_id")


@inject
async def _list_getter(
    dialog_manager: DialogManager,
    listing: FromDishka[ListBdz],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await listing(actor(dialog_manager), _group(dialog_manager))
    items = [
        (
            (
                f"{row.bdz.title} — сдано {row.sent}, ждёт {row.waiting}, "
                f"ИИ {row.published}, ручные {row.manual}"
            ),
            str(row.bdz.bdz_id),
        )
        for row in rows
    ]
    return {"empty": not items, "items": items}


async def _picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["bdz_id"] = item_id
    await manager.switch_to(BdzSG.card)


@inject
async def _card_getter(
    dialog_manager: DialogManager,
    listing: FromDishka[ListBdz],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    bdz_id = _bdz(dialog_manager)
    rows = await listing(actor(dialog_manager), _group(dialog_manager))
    row = next(item for item in rows if item.bdz.bdz_id == bdz_id)
    text = (
        f"<b>{safe(row.bdz.title)}</b>\n"
        f"Срок: {moment(row.bdz.deadline)}\n"
        f"Сдано {row.sent}, ждёт {row.waiting}, ИИ {row.published}, "
        f"у преподавателя {row.manual}, апелляции {row.appealed}, "
        f"итог {row.final}, опоздали {row.late}"
    )
    return {"text": text}


@inject
async def _types_getter(
    dialog_manager: DialogManager,
    types: FromDishka[ListWorkTypes],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await types(actor(dialog_manager), _group(dialog_manager))
    items = [
        (item.title, str(item.work_type_id))
        for item in found
        if item.mode is ScoringMode.PROPORTIONAL
    ]
    return {"empty": not items, "types": items}


async def _type_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["work_type_id"] = item_id
    await manager.switch_to(BdzSG.new_statement)


async def _remember_title(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
) -> None:
    manager.dialog_data["title"] = " ".join(text.split())
    await manager.switch_to(BdzSG.new_type)


async def _pdf(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
) -> None:
    document = message.document
    name = "" if document is None or document.file_name is None else document.file_name
    mime = "" if document is None or document.mime_type is None else document.mime_type
    if document is None or (
        mime != "application/pdf" and not name.lower().endswith(".pdf")
    ):
        _ = await message.answer(_PDF)
        return
    on_statement = manager.current_context().state == BdzSG.new_statement
    key = "statement" if on_statement else "solutions"
    manager.dialog_data[f"{key}_id"] = document.file_id
    manager.dialog_data[f"{key}_unique"] = document.file_unique_id
    nxt = BdzSG.new_solutions if key == "statement" else BdzSG.new_scheme
    await manager.switch_to(nxt)


async def _no_solutions(
    _callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
) -> None:
    _ = manager.dialog_data.pop("solutions_id", None)
    _ = manager.dialog_data.pop("solutions_unique", None)
    await manager.switch_to(BdzSG.new_scheme)


async def _scheme(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
) -> None:
    tasks = parse_scheme(text)
    manager.dialog_data["scheme"] = text
    total = sum((task.max_points for task in tasks), Decimal(0))
    _ = await message.answer(f"Сумма: {points(total)}")
    await manager.switch_to(BdzSG.new_deadline)


@inject
async def _deadline(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
    clock: FromDishka[Clock],
) -> None:
    when = parse_moment(text, clock.now())
    manager.dialog_data["deadline"] = when.isoformat()
    await manager.switch_to(BdzSG.new_confirm)


@inject
async def _confirm_getter(
    dialog_manager: DialogManager,
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    raw = str(dialog_manager.dialog_data["deadline"])
    when = datetime.fromisoformat(raw)
    tasks = parse_scheme(str(dialog_manager.dialog_data["scheme"]))
    total = sum((task.max_points for task in tasks), Decimal(0))
    solved = (
        "PDF приложен"
        if dialog_manager.dialog_data.get("solutions_id")
        else "нет, агент решит сам"
    )
    return {
        "text": (
            f"<b>{safe(dialog_manager.dialog_data['title'])}</b>\n"
            f"Сумма: {points(total)}\n"
            f"Срок: {moment(when)}\n"
            f"Решения: {solved}"
        ),
    }


async def _download(bot: Bot, file_id: str) -> bytes:
    buffer = BytesIO()
    _ = await bot.download(file_id, destination=buffer)
    return buffer.getvalue()


@inject
async def _create(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    create: FromDishka[CreateBdz],
    bot: FromDishka[Bot],
    clock: FromDishka[Clock],
) -> None:
    now = clock.now()
    data = manager.dialog_data
    deadline = datetime.fromisoformat(str(data["deadline"]))
    statement = await _download(bot, str(data["statement_id"]))
    solutions = None
    if data.get("solutions_id"):
        solutions = Upload(
            await _download(bot, str(data["solutions_id"])),
            str(data["solutions_id"]),
            str(data["solutions_unique"]),
            now,
        )
    _ = await create(
        actor(manager),
        _group(manager),
        BdzDraft(
            str(data["title"]),
            deadline,
            uuid.UUID(str(data["work_type_id"])),
            parse_scheme(str(data["scheme"])),
        ),
        Upload(
            statement,
            str(data["statement_id"]),
            str(data["statement_unique"]),
            now,
        ),
        solutions,
    )
    _ = await callback.answer("БДЗ опубликовано.", show_alert=True)
    await manager.switch_to(BdzSG.list)


@inject
async def _move_deadline(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
    update: FromDishka[UpdateBdzDeadline],
    clock: FromDishka[Clock],
) -> None:
    when = parse_moment(text, clock.now())
    _ = await update(actor(manager), _bdz(manager), when)
    await manager.switch_to(BdzSG.card)


@inject
async def _roster_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[BdzRoster],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await roster(actor(dialog_manager), _bdz(dialog_manager))
    lines: list[str] = []
    for row in rows:
        if row.submission is None:
            mark = "не сдано"
        elif row.status is None:
            mark = "ждёт проверки"
        else:
            mark = _status(row.status)
        if row.submission is not None and row.submission.is_late:
            mark += ", опоздал"
        lines.append(f"{safe(row.student.full_name)} — {mark}")
    return {"empty": not lines, "text": "\n".join(lines)}


def _status(status: VerdictStatus) -> str:
    return {
        VerdictStatus.PUBLISHED: "оценка ИИ",
        VerdictStatus.MANUAL: "у преподавателя",
        VerdictStatus.APPEALED: "апелляция",
        VerdictStatus.FINAL: "итог преподавателя",
    }.get(status, status.value)


@inject
async def _export(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    export: FromDishka[ExportBdz],
) -> None:
    path = await export(actor(manager), _bdz(manager))
    if callback.message is not None:
        _ = await callback.message.answer_document(FSInputFile(path))
    manager.show_mode = ShowMode.SEND


@inject
async def _delete(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    delete: FromDishka[DeleteBdz],
) -> None:
    await delete(actor(manager), _bdz(manager))
    _ = await callback.answer("БДЗ удалено.", show_alert=True)
    await manager.switch_to(BdzSG.list)


bdz_dialog = Dialog(
    Window(
        Const("БДЗ группы:"),
        Const("Пока ничего нет.", when="empty"),
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
        SwitchTo(Const("➕ Новое БДЗ"), id="new", state=BdzSG.new_title),
        state=BdzSG.list,
        getter=_list_getter,
    ),
    Window(
        Format("{text}"),
        SwitchTo(Const("📅 Срок"), id="deadline", state=BdzSG.deadline),
        SwitchTo(Const("👥 Кто сдал"), id="roster", state=BdzSG.roster),
        Button(Const("📦 Скачать архив"), id="export", on_click=_export),
        SwitchTo(Const("🗑 Удалить"), id="delete", state=BdzSG.delete),
        SwitchTo(Const("« Список"), id="back", state=BdzSG.list),
        getter=_card_getter,
        state=BdzSG.card,
    ),
    Window(
        Const("Название БДЗ:"),
        TextInput(id="title", on_success=_remember_title),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        state=BdzSG.new_title,
    ),
    Window(
        Const("Вид работы с долей баллов:"),
        Const("В группе нет такого вида.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="type",
                item_id_getter=itemgetter(1),
                items="types",
                on_click=_type_picked,
            ),
            id="types",
            width=1,
            height=6,
        ),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        getter=_types_getter,
        state=BdzSG.new_type,
    ),
    Window(
        Const("Пришлите PDF с условием."),
        MessageInput(_pdf, content_types=[ContentType.DOCUMENT, ContentType.PHOTO]),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        state=BdzSG.new_statement,
    ),
    Window(
        Const(
            "Пришлите PDF с решениями — студенты его не увидят. "
            "Без решений агент сначала решит задачи сам.",
        ),
        MessageInput(_pdf, content_types=[ContentType.DOCUMENT, ContentType.PHOTO]),
        Button(Const("Без решений"), id="no_solutions", on_click=_no_solutions),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        state=BdzSG.new_solutions,
    ),
    Window(
        Const("Разбалловка, например 1:3, 2:5, 3:2"),
        TextInput(id="scheme", on_success=_scheme),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        state=BdzSG.new_scheme,
    ),
    Window(
        Const("Срок, например 07.10 18:30"),
        TextInput(id="deadline", on_success=_deadline),
        SwitchTo(Const("Отмена"), id="cancel", state=BdzSG.list),
        state=BdzSG.new_deadline,
    ),
    Window(
        Format("{text}\nОпубликовать?"),
        Button(Const("Опубликовать"), id="yes", on_click=_create),
        SwitchTo(Const("Отмена"), id="no", state=BdzSG.list),
        getter=_confirm_getter,
        state=BdzSG.new_confirm,
    ),
    Window(
        Const("Новый срок, например 07.10 18:30"),
        TextInput(id="when", on_success=_move_deadline),
        SwitchTo(Const("« Карточка"), id="back", state=BdzSG.card),
        state=BdzSG.deadline,
    ),
    Window(
        Const("Кто сдал:"),
        Const("Пока никто.", when="empty"),
        Format("{text}"),
        SwitchTo(Const("« Карточка"), id="back", state=BdzSG.card),
        getter=_roster_getter,
        state=BdzSG.roster,
    ),
    Window(
        Const("Удалить БДЗ, баллы и все файлы? Это нельзя отменить."),
        Button(Const("Да, удалить"), id="yes", on_click=_delete),
        SwitchTo(Const("Нет"), id="no", state=BdzSG.card),
        state=BdzSG.delete,
    ),
)
