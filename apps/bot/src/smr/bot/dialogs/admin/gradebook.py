"""The scheme of points: work types and caps, tests and their grades, loose points."""

from __future__ import annotations

import dataclasses
import uuid
from decimal import Decimal
from operator import itemgetter
from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
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

from smr.bot.dialogs.common import actor, remembered_id
from smr.bot.parsing import parse_points
from smr.bot.states import GradebookSG
from smr.bot.texts import points, safe
from smr.gradebook.application.contracts import GradebookApi
from smr.gradebook.application.use_cases import (
    EXCUSED,
    AddPoints,
    ApplyDefaultScheme,
    CreateItem,
    CreateWorkType,
    DeleteWorkType,
    GradeInput,
    ItemGrades,
    ListItems,
    ListWorkTypes,
    SetItemGrades,
    UpdateWorkType,
)
from smr.gradebook.domain import GradeEntry, ScoringMode, WorkTypeKind
from smr.roster.application.contracts import RosterApi

_MIDDLEWARE = Any
_KINDS = {
    WorkTypeKind.TEST: "Контрольные",
    WorkTypeKind.HOMEWORK: "Домашние задания",
    WorkTypeKind.ATTENDANCE: "Посещаемость",
    WorkTypeKind.BOARD: "Выходы к доске",
    WorkTypeKind.TEACHER: "Оценка преподавателя",
    WorkTypeKind.OTHER: "Другое",
}
_ACCUMULATING = {WorkTypeKind.BOARD, WorkTypeKind.TEACHER}


def _group(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "group_id")


def _type(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "work_type_id")


@inject
async def _types_getter(
    dialog_manager: DialogManager,
    types: FromDishka[ListWorkTypes],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await types(actor(dialog_manager), _group(dialog_manager))
    total = sum((t.cap for t in found), start=Decimal(0))
    mode = {ScoringMode.PROPORTIONAL: "доля", ScoringMode.ACCUMULATING: "накопительно"}
    return {
        "types": [
            (f"{t.title} · до {points(t.cap)} · {mode[t.mode]}", str(t.work_type_id))
            for t in found
        ],
        "total": points(total) if found else "0",
        "none": not found,
    }


@inject
async def _scheme(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    apply: FromDishka[ApplyDefaultScheme],
) -> None:
    _ = await apply(callback.from_user.id, _group(manager))
    _ = await callback.answer(
        "Схема на 50 баллов создана. Потолки можно поменять.",
        show_alert=True,
    )


async def _type_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["work_type_id"] = item_id
    await manager.switch_to(GradebookSG.work_type)


async def _new_title(
    _m: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    manager.dialog_data["new_title"] = value
    await manager.switch_to(GradebookSG.new_kind)


async def _kinds_getter(**_: _MIDDLEWARE) -> dict[str, object]:
    return {"kinds": [(label, kind.value) for kind, label in _KINDS.items()]}


async def _kind_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["new_kind"] = item_id
    await manager.switch_to(GradebookSG.new_cap)


@inject
async def _new_cap(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    create: FromDishka[CreateWorkType],
) -> None:
    if message.from_user is None:
        return
    try:
        cap = parse_points(value)
    except ValueError:
        _ = await message.answer("Нужно число, например 8.")
        return
    kind = WorkTypeKind(str(manager.dialog_data["new_kind"]))
    work_type = await create(
        message.from_user.id,
        _group(manager),
        title=str(manager.dialog_data["new_title"]),
        kind=kind,
        mode=ScoringMode.ACCUMULATING
        if kind in _ACCUMULATING
        else ScoringMode.PROPORTIONAL,
        cap=cap,
        in_priority=True,
    )
    manager.dialog_data["work_type_id"] = str(work_type.work_type_id)
    await manager.switch_to(GradebookSG.work_type)


@inject
async def _type_getter(
    dialog_manager: DialogManager,
    gradebook: FromDishka[GradebookApi],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    work_type = await gradebook.work_type(_type(dialog_manager))
    if work_type is None:
        return {"text": "Удалено.", "proportional": False, "accumulating": False}
    mode = (
        "доля от выданного"
        if work_type.mode is ScoringMode.PROPORTIONAL
        else "накопительно до потолка"
    )
    return {
        "text": (
            f"<b>{safe(work_type.title)}</b> ({_KINDS[work_type.kind]})\n"
            f"Потолок: {points(work_type.cap)} · {mode}\n"
            f"Учитывается в рандоме у доски: {'да' if work_type.in_priority else 'нет'}"
        ),
        "proportional": work_type.mode is ScoringMode.PROPORTIONAL,
        "accumulating": work_type.mode is ScoringMode.ACCUMULATING,
    }


@inject
async def _cap(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    gradebook: FromDishka[GradebookApi],
    update: FromDishka[UpdateWorkType],
) -> None:
    work_type = await gradebook.work_type(_type(manager))
    if work_type is None or message.from_user is None:
        return
    try:
        cap = parse_points(value)
    except ValueError:
        _ = await message.answer("Нужно число.")
        return
    _ = await update(
        message.from_user.id,
        work_type.work_type_id,
        title=work_type.title,
        cap=cap,
        in_priority=work_type.in_priority,
    )
    await manager.switch_to(GradebookSG.work_type)


@inject
async def _toggle_priority(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    gradebook: FromDishka[GradebookApi],
    update: FromDishka[UpdateWorkType],
) -> None:
    work_type = await gradebook.work_type(_type(manager))
    if work_type is None:
        return
    changed = dataclasses.replace(work_type, in_priority=not work_type.in_priority)
    _ = await update(
        callback.from_user.id,
        changed.work_type_id,
        title=changed.title,
        cap=changed.cap,
        in_priority=changed.in_priority,
    )


@inject
async def _delete(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    delete: FromDishka[DeleteWorkType],
) -> None:
    await delete(callback.from_user.id, _type(manager))
    _ = await callback.answer("Удалено.")
    await manager.switch_to(GradebookSG.types)


@inject
async def _items_getter(
    dialog_manager: DialogManager,
    items: FromDishka[ListItems],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await items(actor(dialog_manager), _type(dialog_manager))
    return {
        "items": [
            (f"{i.title} · макс {points(i.max_points)}", str(i.item_id)) for i in found
        ],
        "empty": not found,
    }


async def _item_title(
    _m: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    manager.dialog_data["item_title"] = value
    await manager.switch_to(GradebookSG.new_item_points)


@inject
async def _item_points(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    create: FromDishka[CreateItem],
) -> None:
    if message.from_user is None:
        return
    try:
        max_points = parse_points(value)
    except ValueError:
        _ = await message.answer("Нужно число, например 8.")
        return
    item = await create(
        message.from_user.id,
        _type(manager),
        title=str(manager.dialog_data["item_title"]),
        max_points=max_points,
    )
    manager.dialog_data["item_id"] = str(item.item_id)
    await manager.switch_to(GradebookSG.grading)


async def _item_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["item_id"] = item_id
    await manager.switch_to(GradebookSG.grading)


@inject
async def _grading_getter(
    dialog_manager: DialogManager,
    grades: FromDishka[ItemGrades],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await grades(
        actor(dialog_manager),
        remembered_id(dialog_manager, "item_id"),
        _group(dialog_manager),
    )

    def mark(entry: GradeEntry | None) -> str:
        if entry is None:
            return "—"
        return "уваж." if entry.excused else points(entry.points)

    return {
        "students": [(f"{s.full_name}: {mark(e)}", str(s.student_id)) for s, e in rows],
    }


async def _grade_student(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["student_id"] = item_id
    await manager.switch_to(GradebookSG.grade_value)


@inject
async def _grade_value(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    set_grades: FromDishka[SetItemGrades],
) -> None:
    if message.from_user is None:
        return
    text = value.strip().lower()
    grade: GradeInput
    if text in {"-", "—", "нет"}:
        grade = None
    elif text in {"н", "у", "уваж"}:
        grade = EXCUSED
    else:
        try:
            grade = parse_points(text)
        except ValueError:
            _ = await message.answer("Число, «у» — уважительная, «-» — убрать оценку.")
            return
    await set_grades(
        message.from_user.id,
        remembered_id(manager, "item_id"),
        {uuid.UUID(str(manager.dialog_data["student_id"])): grade},
    )
    await manager.switch_to(GradebookSG.grading)


@inject
async def _students_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    students = await roster.students_of(_group(dialog_manager))
    return {"students": [(s.full_name, str(s.student_id)) for s in students]}


async def _points_student(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["student_id"] = item_id
    await manager.switch_to(GradebookSG.points_value)


@inject
async def _points_value(
    message: Message,
    _w: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    add: FromDishka[AddPoints],
) -> None:
    if message.from_user is None:
        return
    raw, _, comment = value.strip().partition(" ")
    try:
        given = parse_points(raw)
    except ValueError:
        _ = await message.answer("Начните с баллов: «1» или «1 активность на паре».")
        return
    _ = await add(
        message.from_user.id,
        uuid.UUID(str(manager.dialog_data["student_id"])),
        _type(manager),
        given,
        comment or None,
    )
    _ = await message.answer("Записано.")
    await manager.switch_to(GradebookSG.work_type)


gradebook_dialog = Dialog(
    Window(
        Format("Виды работ группы. Сумма потолков: <b>{total}</b>"),
        Button(
            Const("✨ Схема на 50 баллов"),
            id="scheme",
            on_click=_scheme,
            when="none",
        ),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="type",
                item_id_getter=itemgetter(1),
                items="types",
                on_click=_type_picked,
            ),
            id="types_list",
            width=1,
            height=8,
        ),
        SwitchTo(Const("➕ Вид работы"), id="new", state=GradebookSG.new_title),
        Cancel(Const("« Группа")),
        getter=_types_getter,
        state=GradebookSG.types,
    ),
    Window(
        Const("Название вида работы, например «Коллоквиум»:"),
        TextInput(id="new_title", on_success=_new_title),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.types),
        state=GradebookSG.new_title,
    ),
    Window(
        Const("Что это за работа?"),
        Select(
            Format("{item[0]}"),
            id="kind",
            item_id_getter=itemgetter(1),
            items="kinds",
            on_click=_kind_picked,
        ),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.types),
        getter=_kinds_getter,
        state=GradebookSG.new_kind,
    ),
    Window(
        Const("Потолок в баллах (сколько максимум даёт этот вид работы):"),
        TextInput(id="new_cap", on_success=_new_cap),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.types),
        state=GradebookSG.new_cap,
    ),
    Window(
        Format("{text}"),
        Row(
            SwitchTo(Const("✏️ Потолок"), id="cap", state=GradebookSG.cap),
            Button(
                Const("⚖️ Рандом вкл/выкл"),
                id="priority",
                on_click=_toggle_priority,
            ),
        ),
        SwitchTo(
            Const("🧾 Позиции и оценки"),
            id="items",
            state=GradebookSG.items,
            when="proportional",
        ),
        SwitchTo(
            Const("➕ Баллы студенту"),
            id="points",
            state=GradebookSG.points_student,
            when="accumulating",
        ),
        Button(Const("🗑 Удалить вид работы"), id="delete", on_click=_delete),
        SwitchTo(Const("« Виды работ"), id="back", state=GradebookSG.types),
        getter=_type_getter,
        state=GradebookSG.work_type,
    ),
    Window(
        Const("Новый потолок:"),
        TextInput(id="cap", on_success=_cap),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.work_type),
        state=GradebookSG.cap,
    ),
    Window(
        Const("Позиции (например контрольные). Домашки и занятия появляются тут сами."),
        Const("Позиций пока нет.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="item",
                item_id_getter=itemgetter(1),
                items="items",
                on_click=_item_picked,
            ),
            id="items_list",
            width=1,
            height=8,
        ),
        SwitchTo(Const("➕ Позиция"), id="new", state=GradebookSG.new_item_title),
        SwitchTo(Const("« Вид работы"), id="back", state=GradebookSG.work_type),
        getter=_items_getter,
        state=GradebookSG.items,
    ),
    Window(
        Const("Название, например «Контрольная 1»:"),
        TextInput(id="item_title", on_success=_item_title),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.items),
        state=GradebookSG.new_item_title,
    ),
    Window(
        Const("Максимум баллов за неё:"),
        TextInput(id="item_points", on_success=_item_points),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.items),
        state=GradebookSG.new_item_points,
    ),
    Window(
        Const("Нажмите на студента, чтобы поставить баллы:"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="student",
                item_id_getter=itemgetter(1),
                items="students",
                on_click=_grade_student,
            ),
            id="grading_list",
            width=1,
            height=12,
        ),
        SwitchTo(Const("« Позиции"), id="back", state=GradebookSG.items),
        getter=_grading_getter,
        state=GradebookSG.grading,
    ),
    Window(
        Const("Баллы числом, «у» — уважительная (не считается), «-» — убрать оценку:"),
        TextInput(id="grade", on_success=_grade_value),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.grading),
        state=GradebookSG.grade_value,
    ),
    Window(
        Const("Кому начислить?"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="student",
                item_id_getter=itemgetter(1),
                items="students",
                on_click=_points_student,
            ),
            id="points_list",
            width=1,
            height=12,
        ),
        SwitchTo(Const("« Вид работы"), id="back", state=GradebookSG.work_type),
        getter=_students_getter,
        state=GradebookSG.points_student,
    ),
    Window(
        Const("Баллы и, если нужно, комментарий: «1 активность на паре»"),
        TextInput(id="points", on_success=_points_value),
        SwitchTo(Const("Отмена"), id="cancel", state=GradebookSG.work_type),
        state=GradebookSG.points_value,
    ),
)
