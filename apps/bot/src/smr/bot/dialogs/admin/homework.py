"""Homework: set an assignment, review the queue with the files at hand, grade."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from operator import itemgetter
from typing import Any

from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, FSInputFile, Message
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
from smr.bot.parsing import parse_moment, parse_points
from smr.bot.states import HomeworkSG
from smr.bot.texts import moment, points, safe
from smr.core.clock import Clock
from smr.homework.application.use_cases import (
    AssignmentDraft,
    AssignmentRoster,
    CopyAssignment,
    CreateAssignment,
    DeleteAssignment,
    ExportSubmissions,
    GradeSubmission,
    ListAssignments,
    OpenSubmission,
    ReviewQueue,
    Upload,
)
from smr.homework.domain import SubmissionStatus
from smr.roster.application.use_cases import ListGroups

_MIDDLEWARE = Any


def _group(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "group_id")


@inject
async def _list_getter(
    dialog_manager: DialogManager,
    assignments: FromDishka[ListAssignments],
    queue: FromDishka[ReviewQueue],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    who = actor(dialog_manager)
    found = await assignments(who, _group(dialog_manager))
    waiting = await queue(who, _group(dialog_manager))
    return {
        "assignments": [
            (
                (
                    f"{s.assignment.title} · до {moment(s.assignment.deadline)} · "
                    f"сдали {s.submitted}, проверено {s.graded}"
                ),
                str(s.assignment.assignment_id),
            )
            for s in found
        ],
        "empty": not found,
        "waiting": len(waiting),
    }


async def _assignment_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["assignment_id"] = item_id
    await manager.switch_to(HomeworkSG.assignment)


async def _review_all(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
) -> None:
    _ = callback
    manager.dialog_data.pop("only_assignment", None)
    await manager.switch_to(HomeworkSG.review)


async def _review_this(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
) -> None:
    _ = callback
    manager.dialog_data["only_assignment"] = manager.dialog_data["assignment_id"]
    await manager.switch_to(HomeworkSG.review)


async def _title(
    _m: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    manager.dialog_data["title"] = value
    await manager.switch_to(HomeworkSG.new_body)


async def _body(
    _m: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    manager.dialog_data["body"] = "" if value.strip() == "-" else value
    await manager.switch_to(HomeworkSG.new_deadline)


@inject
async def _deadline(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    clock: FromDishka[Clock],
) -> None:
    try:
        manager.dialog_data["deadline"] = parse_moment(value, clock.now()).isoformat()
    except ValueError:
        _ = await message.answer("Дата вида 07.10 или 07.10 23:59.")
        return
    await manager.switch_to(HomeworkSG.new_points)


async def _points(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    try:
        manager.dialog_data["max_points"] = str(parse_points(value))
    except ValueError:
        _ = await message.answer("Нужно число, например 3.")
        return
    await manager.switch_to(HomeworkSG.new_file)


async def _statement(
    message: Message,
    _w: MessageInput,
    manager: DialogManager,
) -> None:
    if message.bot is None:
        return
    received = await receive(message.bot, message)
    if received is None:
        _ = await message.answer("Пришлите файл или нажмите «Без файла».")
        return
    manager.dialog_data["statement"] = {
        "tg_file_id": received.tg_file_id,
        "unique": received.tg_file_unique_id,
    }
    # The bytes are fetched again on confirmation; dialog data stays small.
    await manager.switch_to(HomeworkSG.new_confirm)


async def _confirm_getter(
    dialog_manager: DialogManager,
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    data = dialog_manager.dialog_data
    return {
        "title": safe(data.get("title", "")),
        "deadline": moment(datetime.fromisoformat(str(data["deadline"]))),
        "points": data.get("max_points", ""),
        "file": "есть" if data.get("statement") else "нет",
    }


@inject
async def _create(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    create: FromDishka[CreateAssignment],
) -> None:
    data = manager.dialog_data
    statement = None
    raw = data.get("statement")
    if isinstance(raw, dict) and callback.bot is not None:
        downloaded = await callback.bot.download(str(raw["tg_file_id"]))
        if downloaded is not None:
            statement = Upload(
                downloaded.read(),
                str(raw["tg_file_id"]),
                str(raw["unique"]),
                datetime.fromisoformat(str(data["deadline"])),
            )
    assignment = await create(
        callback.from_user.id,
        _group(manager),
        AssignmentDraft(
            title=str(data["title"]),
            body=str(data.get("body", "")),
            deadline=datetime.fromisoformat(str(data["deadline"])),
            max_points=Decimal(str(data["max_points"])),
        ),
        statement=statement,
    )
    _ = await callback.answer(
        "Задание опубликовано, группа получит уведомление.",
        show_alert=True,
    )
    manager.dialog_data["assignment_id"] = str(assignment.assignment_id)
    for key in ("title", "body", "deadline", "max_points", "statement"):
        _ = manager.dialog_data.pop(key, None)
    await manager.switch_to(HomeworkSG.assignment)


@inject
async def _assignment_getter(
    dialog_manager: DialogManager,
    assignments: FromDishka[ListAssignments],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    target = remembered_id(dialog_manager, "assignment_id")
    found = await assignments(actor(dialog_manager), _group(dialog_manager))
    summary = next((s for s in found if s.assignment.assignment_id == target), None)
    if summary is None:
        return {"text": "Задание удалено."}
    a = summary.assignment
    return {
        "text": (
            f"<b>{safe(a.title)}</b>\n"
            f"Срок: {moment(a.deadline)} · максимум {points(a.max_points)}\n"
            f"Сдали: {summary.submitted} (с опозданием {summary.late}), "
            f"проверено: {summary.graded}"
        ),
    }


@inject
async def _roster_getter(
    dialog_manager: DialogManager,
    roster_view: FromDishka[AssignmentRoster],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await roster_view(
        actor(dialog_manager),
        remembered_id(dialog_manager, "assignment_id"),
    )
    lines = []
    for student, submission in rows:
        if submission is None:
            mark = "⬜"
        elif submission.status is SubmissionStatus.GRADED:
            mark = "✅"
        else:
            mark = "⏰" if submission.is_late else "📨"
        lines.append(f"{mark} {safe(student.full_name)}")
    return {"text": "\n".join(lines) or "Список пуст."}


@inject
async def _export(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    export: FromDishka[ExportSubmissions],
) -> None:
    target = await export(
        callback.from_user.id,
        remembered_id(manager, "assignment_id"),
    )
    if callback.message is not None:
        _ = await callback.message.answer_document(
            FSInputFile(target),
            caption="Работы по папкам с ФИО (копия в data/exports).",
        )
    manager.show_mode = ShowMode.SEND


@inject
async def _groups_getter(
    dialog_manager: DialogManager,
    groups: FromDishka[ListGroups],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await groups(actor(dialog_manager), include_archived=False)
    here = _group(dialog_manager)
    return {"groups": [(g.name, str(g.group_id)) for g in found if g.group_id != here]}


async def _copy_target(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["copy_to"] = item_id
    await manager.switch_to(HomeworkSG.copy_deadline)


@inject
async def _copy(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    copy: FromDishka[CopyAssignment],
    clock: FromDishka[Clock],
) -> None:
    if message.from_user is None:
        return
    try:
        deadline = parse_moment(value, clock.now())
    except ValueError:
        _ = await message.answer("Дата вида 07.10 или 07.10 23:59.")
        return
    _ = await copy(
        message.from_user.id,
        remembered_id(manager, "assignment_id"),
        uuid.UUID(str(manager.dialog_data["copy_to"])),
        deadline,
    )
    _ = await message.answer("Скопировано, та группа получит уведомление.")
    await manager.switch_to(HomeworkSG.assignment)


@inject
async def _delete(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    delete: FromDishka[DeleteAssignment],
) -> None:
    await delete(callback.from_user.id, remembered_id(manager, "assignment_id"))
    _ = await callback.answer(
        "Задание удалено вместе с работами и баллами.",
        show_alert=True,
    )
    await manager.switch_to(HomeworkSG.list)


@inject
async def _review_getter(
    dialog_manager: DialogManager,
    queue: FromDishka[ReviewQueue],
    open_submission: FromDishka[OpenSubmission],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    who = actor(dialog_manager)
    waiting = list(await queue(who, _group(dialog_manager)))
    only = dialog_manager.dialog_data.get("only_assignment")
    if only is not None:
        waiting = [s for s in waiting if str(s.assignment_id) == only]
    if not waiting:
        dialog_manager.dialog_data.pop("submission_id", None)
        return {"text": "🎉 Всё проверено.", "has": False}
    current = waiting[0]
    dialog_manager.dialog_data["submission_id"] = str(current.submission_id)
    review = await open_submission(who, current.submission_id)
    sent = "" if current.sent_at is None else moment(current.sent_at)
    late = " · ⏰ после срока" if current.is_late else ""
    return {
        "text": (
            f"<b>{safe(review.student.full_name)}</b> — "
            f"{safe(review.assignment.title)}\n"
            f"Версия {current.version}, отправлено {sent}{late}\n"
            f"Файлов: {len(review.files)} · "
            f"максимум {points(review.assignment.max_points)}\n"
            f"В очереди: {len(waiting)}"
        ),
        "has": True,
    }


@inject
async def _show_files(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    open_submission: FromDishka[OpenSubmission],
) -> None:
    review = await open_submission(
        callback.from_user.id,
        uuid.UUID(str(manager.dialog_data["submission_id"])),
    )
    for file in review.files:
        await send_file(callback.message, file.tg_file_id, file.kind)
    manager.show_mode = ShowMode.SEND


@inject
async def _grade(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    grade: FromDishka[GradeSubmission],
) -> None:
    if message.from_user is None:
        return
    raw, _, comment = value.strip().partition(" ")
    try:
        given = parse_points(raw)
    except ValueError:
        _ = await message.answer("Начните с баллов: «2.5» или «2.5 комментарий».")
        return
    _ = await grade(
        message.from_user.id,
        uuid.UUID(str(manager.dialog_data["submission_id"])),
        given,
        comment or None,
    )
    _ = await message.answer(f"Оценено: {points(given)}. Студент получит уведомление.")
    await manager.switch_to(HomeworkSG.review)


homework_dialog = Dialog(
    Window(
        Const("Домашние задания группы:"),
        Const("Заданий пока нет.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="assignment",
                item_id_getter=itemgetter(1),
                items="assignments",
                on_click=_assignment_picked,
            ),
            id="assignments_list",
            width=1,
            height=8,
        ),
        Button(Format("📥 На проверку ({waiting})"), id="review", on_click=_review_all),
        SwitchTo(Const("➕ Новое ДЗ"), id="new", state=HomeworkSG.new_title),
        Cancel(Const("« Группа")),
        getter=_list_getter,
        state=HomeworkSG.list,
    ),
    Window(
        Const("Название, например «ДЗ к семинару 3»:"),
        TextInput(id="title", on_success=_title),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        state=HomeworkSG.new_title,
    ),
    Window(
        Const("Текст задания (или «-», если условие будет файлом):"),
        TextInput(id="body", on_success=_body),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        state=HomeworkSG.new_body,
    ),
    Window(
        Const("Срок сдачи, например 07.10 23:59 (без времени — до 23:59):"),
        TextInput(id="deadline", on_success=_deadline),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        state=HomeworkSG.new_deadline,
    ),
    Window(
        Const("Максимум баллов за это задание:"),
        TextInput(id="points", on_success=_points),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        state=HomeworkSG.new_points,
    ),
    Window(
        Const("Пришлите файл с условием (PDF), или нажмите «Без файла»."),
        MessageInput(
            _statement,
            content_types=[ContentType.DOCUMENT, ContentType.PHOTO],
        ),
        SwitchTo(Const("Без файла"), id="skip", state=HomeworkSG.new_confirm),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        state=HomeworkSG.new_file,
    ),
    Window(
        Format(
            "Опубликовать?\n<b>{title}</b>\nСрок: {deadline}\n"
            "Максимум: {points}\nФайл: {file}",
        ),
        Button(
            Const("✅ Опубликовать и уведомить группу"),
            id="create",
            on_click=_create,
        ),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.list),
        getter=_confirm_getter,
        state=HomeworkSG.new_confirm,
    ),
    Window(
        Format("{text}"),
        Button(Const("📥 Проверять это ДЗ"), id="review", on_click=_review_this),
        Row(
            SwitchTo(Const("👥 Кто сдал"), id="roster", state=HomeworkSG.roster),
            Button(Const("📦 Скачать zip"), id="export", on_click=_export),
        ),
        Row(
            SwitchTo(Const("📋 Копировать"), id="copy", state=HomeworkSG.copy),
            SwitchTo(Const("🗑 Удалить"), id="delete", state=HomeworkSG.delete),
        ),
        SwitchTo(Const("« Задания"), id="back", state=HomeworkSG.list),
        getter=_assignment_getter,
        state=HomeworkSG.assignment,
    ),
    Window(
        Format("✅ проверено · 📨 сдано · ⏰ после срока · ⬜ нет\n\n{text}"),
        SwitchTo(Const("« Задание"), id="back", state=HomeworkSG.assignment),
        getter=_roster_getter,
        state=HomeworkSG.roster,
    ),
    Window(
        Const("В какую группу скопировать?"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="target",
                item_id_getter=itemgetter(1),
                items="groups",
                on_click=_copy_target,
            ),
            id="targets",
            width=1,
            height=6,
        ),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.assignment),
        getter=_groups_getter,
        state=HomeworkSG.copy,
    ),
    Window(
        Const("Срок для той группы, например 08.10 23:59:"),
        TextInput(id="copy_deadline", on_success=_copy),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.assignment),
        state=HomeworkSG.copy_deadline,
    ),
    Window(
        Const("Удалить задание вместе со всеми работами и баллами за него?"),
        Button(Const("Да, удалить"), id="yes", on_click=_delete),
        Button(Const("Нет"), id="no", on_click=go(HomeworkSG.assignment)),
        state=HomeworkSG.delete,
    ),
    Window(
        Format("{text}"),
        Button(
            Const("📎 Показать файлы"),
            id="files",
            on_click=_show_files,
            when="has",
        ),
        SwitchTo(Const("✍️ Оценить"), id="grade", state=HomeworkSG.grade, when="has"),
        SwitchTo(Const("« Задания"), id="back", state=HomeworkSG.list),
        getter=_review_getter,
        state=HomeworkSG.review,
    ),
    Window(
        Const("Баллы и, если нужно, комментарий: «2.5 нет пункта б»"),
        TextInput(id="grade", on_success=_grade),
        SwitchTo(Const("Отмена"), id="cancel", state=HomeworkSG.review),
        state=HomeworkSG.grade,
    ),
)
