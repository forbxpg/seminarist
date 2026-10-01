"""Sessions: create one, mark attendance, call students to the board, grade answers."""

from __future__ import annotations

import uuid
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

from smr.bot.dialogs.common import actor, go, remembered_id
from smr.bot.parsing import parse_moment, parse_points
from smr.bot.states import SessionsSG
from smr.bot.texts import moment, safe
from smr.core.clock import Clock
from smr.sessions.application.use_cases import (
    AttendanceSheet,
    BoardCandidates,
    CallToBoard,
    CreateSession,
    DeleteBoardCall,
    DrawToBoard,
    GradeBoardCall,
    ListSessions,
    MarkAttendance,
    SessionCalls,
)
from smr.sessions.domain import AttendanceStatus, BoardMode, NoCandidatesError

_MIDDLEWARE = Any
_NEXT = {
    AttendanceStatus.PRESENT: AttendanceStatus.ABSENT,
    AttendanceStatus.ABSENT: AttendanceStatus.EXCUSED,
    AttendanceStatus.EXCUSED: AttendanceStatus.PRESENT,
}
_ICON = {
    AttendanceStatus.PRESENT: "✅",
    AttendanceStatus.ABSENT: "❌",
    AttendanceStatus.EXCUSED: "🟡",
}


def _session(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "session_id")


@inject
async def _list_getter(
    dialog_manager: DialogManager,
    sessions: FromDishka[ListSessions],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await sessions(
        actor(dialog_manager),
        remembered_id(dialog_manager, "group_id"),
    )
    return {
        "sessions": [
            (f"{moment(s.starts_at)} · {s.topic}", str(s.session_id)) for s in found
        ],
        "empty": not found,
    }


async def _session_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["session_id"] = item_id
    manager.dialog_data.pop("marks", None)
    await manager.switch_to(SessionsSG.session)


@inject
async def _when(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    clock: FromDishka[Clock],
) -> None:
    now = clock.now()
    try:
        starts = now if value.strip().lower() == "сейчас" else parse_moment(value, now)
    except ValueError:
        _ = await message.answer("Напишите «сейчас» или дату вида 07.10 10:15.")
        return
    manager.dialog_data["starts_at"] = starts.isoformat()
    await manager.switch_to(SessionsSG.new_topic)


@inject
async def _create(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    create: FromDishka[CreateSession],
) -> None:
    from datetime import datetime  # ruff: ignore[import-outside-top-level] -- only here

    if message.from_user is None:
        return
    session = await create(
        message.from_user.id,
        remembered_id(manager, "group_id"),
        starts_at=datetime.fromisoformat(str(manager.dialog_data["starts_at"])),
        topic=value,
    )
    manager.dialog_data["session_id"] = str(session.session_id)
    manager.dialog_data.pop("marks", None)
    await manager.switch_to(SessionsSG.session)


@inject
async def _attendance_getter(
    dialog_manager: DialogManager,
    sheet: FromDishka[AttendanceSheet],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await sheet(actor(dialog_manager), _session(dialog_manager))
    marks: dict[str, str] = dialog_manager.dialog_data.setdefault(
        "marks",
        {str(student.student_id): status.value for student, status in rows},
    )
    return {
        "students": [
            (
                f"{_ICON[AttendanceStatus(marks[str(s.student_id)])]} {s.full_name}",
                str(s.student_id),
            )
            for s, _status in rows
        ],
    }


async def _cycle(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    marks: dict[str, str] = manager.dialog_data["marks"]
    marks[item_id] = _NEXT[AttendanceStatus(marks[item_id])].value


@inject
async def _save_attendance(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    mark: FromDishka[MarkAttendance],
) -> None:
    marks: dict[str, str] = manager.dialog_data.get("marks", {})
    await mark(
        callback.from_user.id,
        _session(manager),
        {uuid.UUID(sid): AttendanceStatus(status) for sid, status in marks.items()},
    )
    absent = sum(
        1 for status in marks.values() if status != AttendanceStatus.PRESENT.value
    )
    _ = await callback.answer(f"Сохранено. Отсутствуют/уважительно: {absent}.")
    await manager.switch_to(SessionsSG.session)


@inject
async def _board_getter(
    dialog_manager: DialogManager,
    candidates: FromDishka[BoardCandidates],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await candidates(actor(dialog_manager), _session(dialog_manager))
    return {
        "candidates": [
            (
                f"{c.student.full_name} · {c.probability:.0%} · выходов {c.calls}",
                str(c.student.student_id),
            )
            for c in found
        ],
        "empty": not found,
    }


@inject
async def _manual(
    callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
    call: FromDishka[CallToBoard],
) -> None:
    called = await call(
        callback.from_user.id,
        _session(manager),
        uuid.UUID(item_id),
        BoardMode.MANUAL,
        None,
    )
    manager.dialog_data["call_id"] = str(called.call_id)
    await manager.switch_to(SessionsSG.grade)


@inject
async def _draw(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    draw: FromDishka[DrawToBoard],
) -> None:
    try:
        drawn = await draw(callback.from_user.id, _session(manager))
    except NoCandidatesError:
        _ = await callback.answer("Все присутствующие уже выходили.", show_alert=True)
        return
    manager.dialog_data["drawn_id"] = str(drawn.student.student_id)
    manager.dialog_data["drawn_name"] = drawn.student.full_name
    manager.dialog_data["drawn_chance"] = f"{drawn.probability:.0%}"
    await manager.switch_to(SessionsSG.drawn)


async def _drawn_getter(
    dialog_manager: DialogManager,
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    data = dialog_manager.dialog_data
    return {
        "name": safe(data.get("drawn_name", "")),
        "chance": data.get("drawn_chance", ""),
    }


@inject
async def _confirm_draw(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    call: FromDishka[CallToBoard],
) -> None:
    called = await call(
        callback.from_user.id,
        _session(manager),
        uuid.UUID(str(manager.dialog_data["drawn_id"])),
        BoardMode.RANDOM,
        None,
    )
    manager.dialog_data["call_id"] = str(called.call_id)
    await manager.switch_to(SessionsSG.grade)


@inject
async def _graded(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    grade: FromDishka[GradeBoardCall],
) -> None:
    if message.from_user is None:
        return
    try:
        points = parse_points(value)
    except ValueError:
        _ = await message.answer("Нужно число баллов, например 1 или 1.5.")
        return
    _ = await grade(
        message.from_user.id,
        uuid.UUID(str(manager.dialog_data["call_id"])),
        points,
        None,
    )
    _ = await message.answer("Баллы записаны.")
    await manager.switch_to(SessionsSG.board)


@inject
async def _calls_getter(
    dialog_manager: DialogManager,
    calls: FromDishka[SessionCalls],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await calls(actor(dialog_manager), _session(dialog_manager))
    icon = {BoardMode.MANUAL: "👆", BoardMode.RANDOM: "🎲"}
    return {
        "calls": [
            (
                f"{icon[c.mode]} {s.full_name} · "
                + ("оценено" if c.entry_id else "без баллов"),
                str(c.call_id),
            )
            for c, s in found
        ],
        "empty": not found,
    }


async def _call_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["call_id"] = item_id
    await manager.switch_to(SessionsSG.grade)


@inject
async def _delete_call(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    delete: FromDishka[DeleteBoardCall],
) -> None:
    await delete(callback.from_user.id, uuid.UUID(str(manager.dialog_data["call_id"])))
    _ = await callback.answer("Вызов удалён.")
    await manager.switch_to(SessionsSG.calls)


sessions_dialog = Dialog(
    Window(
        Const("Занятия группы:"),
        Const("Занятий пока нет.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="session",
                item_id_getter=itemgetter(1),
                items="sessions",
                on_click=_session_picked,
            ),
            id="sessions_list",
            width=1,
            height=8,
        ),
        SwitchTo(Const("➕ Новое занятие"), id="new", state=SessionsSG.new_when),
        Cancel(Const("« Группа")),
        getter=_list_getter,
        state=SessionsSG.list,
    ),
    Window(
        Const("Когда занятие? «сейчас» или дата, например 07.10 10:15"),
        TextInput(id="when", on_success=_when),
        SwitchTo(Const("Отмена"), id="cancel", state=SessionsSG.list),
        state=SessionsSG.new_when,
    ),
    Window(
        Const("Тема занятия:"),
        TextInput(id="topic", on_success=_create),
        SwitchTo(Const("Отмена"), id="cancel", state=SessionsSG.list),
        state=SessionsSG.new_topic,
    ),
    Window(
        Const("Занятие"),
        Row(
            SwitchTo(
                Const("✅ Посещаемость"),
                id="attendance",
                state=SessionsSG.attendance,
            ),
            SwitchTo(Const("🎓 К доске"), id="board", state=SessionsSG.board),
        ),
        SwitchTo(Const("📋 Вызовы и баллы"), id="calls", state=SessionsSG.calls),
        SwitchTo(Const("« Занятия"), id="back", state=SessionsSG.list),
        state=SessionsSG.session,
    ),
    Window(
        Const("Нажимайте на студента: ✅ был → ❌ не был → 🟡 уважительная."),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="mark",
                item_id_getter=itemgetter(1),
                items="students",
                on_click=_cycle,
            ),
            id="marks_list",
            width=1,
            height=12,
        ),
        Button(Const("💾 Сохранить"), id="save", on_click=_save_attendance),
        SwitchTo(Const("« Занятие"), id="back", state=SessionsSG.session),
        getter=_attendance_getter,
        state=SessionsSG.attendance,
    ),
    Window(
        Const(
            "Кого вызвать? Шанс в рандоме выше у тех,\n"
            "кто реже выходил и у кого ниже баллы.",
        ),
        Const("Все присутствующие уже выходили.", when="empty"),
        Button(Const("🎲 Рандом"), id="draw", on_click=_draw),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="candidate",
                item_id_getter=itemgetter(1),
                items="candidates",
                # dishka's inject types the widget as ManagedWidget, Select wants itself
                on_click=_manual,  # pyright: ignore[reportArgumentType]
            ),
            id="candidates_list",
            width=1,
            height=10,
        ),
        SwitchTo(Const("« Занятие"), id="back", state=SessionsSG.session),
        getter=_board_getter,
        state=SessionsSG.board,
    ),
    Window(
        Format("🎲 Выпал(а): <b>{name}</b> (шанс был {chance})"),
        Button(Const("✅ Вызвать"), id="confirm", on_click=_confirm_draw),
        Button(Const("🎲 Ещё раз"), id="again", on_click=_draw),
        SwitchTo(Const("« Доска"), id="back", state=SessionsSG.board),
        getter=_drawn_getter,
        state=SessionsSG.drawn,
    ),
    Window(
        Const("Сколько баллов за ответ? Напишите число, или нажмите «Без баллов»."),
        TextInput(id="points", on_success=_graded),
        Row(
            Button(Const("Без баллов"), id="skip", on_click=go(SessionsSG.board)),
            Button(Const("🗑 Удалить вызов"), id="delete", on_click=_delete_call),
        ),
        state=SessionsSG.grade,
    ),
    Window(
        Const("Вызовы этого занятия (нажмите, чтобы поставить или изменить баллы):"),
        Const("Вызовов пока не было.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="call",
                item_id_getter=itemgetter(1),
                items="calls",
                on_click=_call_picked,
            ),
            id="calls_list",
            width=1,
            height=10,
        ),
        SwitchTo(Const("« Занятие"), id="back", state=SessionsSG.session),
        getter=_calls_getter,
        state=SessionsSG.calls,
    ),
)
