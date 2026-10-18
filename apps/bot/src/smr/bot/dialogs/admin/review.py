"""The teacher's queue: a manual check or an appeal, then a final grade."""

from __future__ import annotations

import uuid
from decimal import Decimal
from operator import itemgetter
from typing import Any

from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import actor, remembered_id
from smr.bot.parsing import parse_scores
from smr.bot.states import ReviewSG
from smr.bot.texts import safe
from smr.core.files import FileStore
from smr.review.application.use_cases import (
    FinalizeByTeacher,
    OpenForTeacher,
    TeacherQueue,
)

_MIDDLEWARE = Any


def _verdict(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "verdict_id")


@inject
async def _queue_getter(
    dialog_manager: DialogManager,
    queue: FromDishka[TeacherQueue],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await queue(actor(dialog_manager))
    items = []
    for row in rows:
        mark = "апелляция" if row.appeal is not None else "ручная"
        late = ", опоздал" if row.is_late else ""
        label = f"{row.title} v{row.version} — {mark}{late}"
        items.append((label, str(row.verdict.verdict_id)))
    return {"empty": not items, "items": items, "count": len(items)}


@inject
async def _picked(
    callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
    opened: FromDishka[OpenForTeacher],
    files: FromDishka[FileStore],
) -> None:
    manager.dialog_data["verdict_id"] = item_id
    view = await opened(actor(manager), uuid.UUID(item_id))
    manager.dialog_data["work_path"] = view.work_path
    if callback.message is not None:
        document = FSInputFile(files.path(view.work_path))
        _ = await callback.message.answer_document(document)
    manager.show_mode = ShowMode.SEND
    await manager.switch_to(ReviewSG.item)


@inject
async def _item_getter(
    dialog_manager: DialogManager,
    opened: FromDishka[OpenForTeacher],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    view = await opened(actor(dialog_manager), _verdict(dialog_manager))
    lines = [
        f"<b>{safe(view.sheet.title)}</b>",
        safe(view.verdict.summary) if view.verdict.summary else "",
        *(
            f"Задача {task.number}: {task.points} из {task.max_points} — "
            f"{safe(task.explanation)}"
            for task in view.verdict.tasks
        ),
    ]
    if view.appeal is not None:
        lines.append(f"Апелляция: {safe(view.appeal.text)}")
    dialog_manager.dialog_data["numbers"] = [task.number for task in view.sheet.scheme]
    dialog_manager.dialog_data["work_path"] = view.work_path
    return {"text": "\n".join(line for line in lines if line)}


@inject
async def _send_pdf(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    files: FromDishka[FileStore],
) -> None:
    path = files.path(str(manager.dialog_data["work_path"]))
    if callback.message is not None:
        _ = await callback.message.answer_document(FSInputFile(path))
    manager.show_mode = ShowMode.SEND


async def _scores(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
) -> None:
    numbers = [int(number) for number in manager.dialog_data["numbers"]]
    scores = parse_scores(text, numbers)
    manager.dialog_data["scores"] = {
        str(number): str(value) for number, value in scores.items()
    }
    await manager.switch_to(ReviewSG.comment)


async def _comment(
    _message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    text: str,
) -> None:
    manager.dialog_data["comment"] = "" if text.strip() == "." else text.strip()
    await manager.switch_to(ReviewSG.confirm)


@inject
async def _finalize(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    finalize: FromDishka[FinalizeByTeacher],
) -> None:
    raw = manager.dialog_data["scores"]
    scores = {int(number): Decimal(value) for number, value in raw.items()}
    _ = await finalize(
        actor(manager),
        _verdict(manager),
        scores,
        {},
        str(manager.dialog_data.get("comment", "")),
    )
    _ = await callback.answer("Оценка отправлена студенту.", show_alert=True)
    await manager.switch_to(ReviewSG.queue)


review_dialog = Dialog(
    Window(
        Const("Ручная проверка:"),
        Const("Очередь пуста.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="item",
                item_id_getter=itemgetter(1),
                items="items",
                on_click=_picked,  # pyright: ignore[reportArgumentType]
            ),
            id="queue",
            width=1,
            height=6,
        ),
        getter=_queue_getter,
        state=ReviewSG.queue,
    ),
    Window(
        Format("{text}"),
        Button(Const("📄 Работа"), id="pdf", on_click=_send_pdf),
        SwitchTo(Const("Оценить"), id="grade", state=ReviewSG.grade),
        SwitchTo(Const("« Очередь"), id="back", state=ReviewSG.queue),
        getter=_item_getter,
        state=ReviewSG.item,
    ),
    Window(
        Const("Баллы по задачам, например 1:3 2:0 3:2"),
        TextInput(id="scores", on_success=_scores),
        SwitchTo(Const("Отмена"), id="cancel", state=ReviewSG.item),
        state=ReviewSG.grade,
    ),
    Window(
        Const("Комментарий студенту. Можно отправить точку, если комментария нет."),
        TextInput(id="comment", on_success=_comment),
        SwitchTo(Const("Отмена"), id="cancel", state=ReviewSG.item),
        state=ReviewSG.comment,
    ),
    Window(
        Const("Отправить эту оценку? Она окончательная."),
        Button(Const("Отправить"), id="yes", on_click=_finalize),
        SwitchTo(Const("Отмена"), id="no", state=ReviewSG.item),
        state=ReviewSG.confirm,
    ),
)
