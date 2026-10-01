"""A bound student's menu: homework, seminars, scores, settings."""

from __future__ import annotations

import json
import uuid
from operator import itemgetter
from typing import Any

from aiogram.enums import ContentType
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import actor, go, remembered_id
from smr.bot.files import receive, send_file
from smr.bot.states import StudentSG
from smr.bot.texts import moment, points, safe
from smr.core.files import FileTooLargeError, UnsupportedFileError
from smr.gradebook.application.use_cases import StudentReport
from smr.homework.application.use_cases import (
    AddFile,
    ClearDraft,
    DeleteStudentFiles,
    MyWork,
    StudentAssignments,
    StudentWork,
    Submit,
    Upload,
)
from smr.homework.domain import (
    DraftEmptyError,
    SubmissionClosedError,
    SubmissionStatus,
    TooManyFilesError,
)
from smr.materials.application.use_cases import MaterialFiles, PublishedMaterials
from smr.notifications.application.use_cases import RemindersEnabled, SetReminders
from smr.roster.application.use_cases import ForgetAccount, Memberships
from smr.roster.domain import BindingStatus

_MIDDLEWARE = Any


def _group(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "group_id")


@inject
async def _groups_getter(
    dialog_manager: DialogManager,
    memberships: FromDishka[Memberships],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = [
        m
        for m in await memberships(actor(dialog_manager))
        if m.student.binding is BindingStatus.BOUND
    ]
    return {"groups": [(m.group.name, str(m.group.group_id)) for m in rows]}


async def _group_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["group_id"] = item_id
    await manager.switch_to(StudentSG.menu)


@inject
async def _menu_getter(
    dialog_manager: DialogManager,
    memberships: FromDishka[Memberships],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    group_id = _group(dialog_manager)
    rows = await memberships(actor(dialog_manager))
    mine = next((m for m in rows if m.group.group_id == group_id), None)
    bound = [m for m in rows if m.student.binding is BindingStatus.BOUND]
    return {
        "group": safe(mine.group.name if mine else ""),
        "name": safe(mine.student.full_name if mine else ""),
        "several": len(bound) > 1,
    }


def _status(work: StudentWork) -> str:
    live = work.live
    if live is None:
        return "📎 черновик" if work.draft_files else "⬜ не сдано"
    if live.status is SubmissionStatus.GRADED and work.points is not None:
        return f"✅ {points(work.points)}/{points(work.assignment.max_points)}"
    return "⏰ сдано с опозданием" if live.is_late else "📨 сдано"


@inject
async def _homework_getter(
    dialog_manager: DialogManager,
    assignments: FromDishka[StudentAssignments],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    works = await assignments(actor(dialog_manager), _group(dialog_manager))
    return {
        "works": [
            (
                f"{work.assignment.title} · до {moment(work.assignment.deadline)} · "
                + _status(work),
                str(work.assignment.assignment_id),
            )
            for work in works
        ],
        "empty": not works,
    }


async def _assignment_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["assignment_id"] = item_id
    await manager.switch_to(StudentSG.assignment)


@inject
async def _assignment_getter(
    dialog_manager: DialogManager,
    work: FromDishka[MyWork],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    state = await work(
        actor(dialog_manager),
        remembered_id(dialog_manager, "assignment_id"),
    )
    assignment = state.assignment
    lines = [
        f"<b>{safe(assignment.title)}</b>",
        (
            f"Срок: {moment(assignment.deadline)} (МСК) · "
            f"максимум {points(assignment.max_points)}"
        ),
    ]
    if assignment.body:
        lines.append(f"\n{safe(assignment.body)}")
    lines.append(f"\nСтатус: {_status(state)}")
    if state.live is not None and state.live.sent_at is not None:
        lines.append(f"Сдано: {moment(state.live.sent_at)}, файлов: {state.live_files}")
    if state.comment:
        lines.append(f"Комментарий преподавателя: {safe(state.comment)}")
    if state.draft_files:
        lines.append(f"В черновике файлов: {state.draft_files} — нажмите «Сдать».")
    graded = state.live is not None and state.live.status is SubmissionStatus.GRADED
    return {
        "text": "\n".join(lines),
        "can_add": not graded,
        "can_submit": state.draft_files > 0,
        "has_statement": assignment.statement is not None,
    }


@inject
async def _send_statement(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    work: FromDishka[MyWork],
) -> None:
    state = await work(callback.from_user.id, remembered_id(manager, "assignment_id"))
    statement = state.assignment.statement
    if statement is not None:
        await send_file(callback.message, statement.tg_file_id, statement.kind)
    manager.show_mode = ShowMode.SEND


@inject
async def _submit(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    submit: FromDishka[Submit],
) -> None:
    try:
        submitted = await submit(
            callback.from_user.id,
            remembered_id(manager, "assignment_id"),
        )
    except DraftEmptyError:
        _ = await callback.answer("Сначала добавьте файлы.", show_alert=True)
        return
    except SubmissionClosedError:
        _ = await callback.answer("Работа уже проверена.", show_alert=True)
        return
    late = " (после срока)" if submitted.is_late else ""
    _ = await callback.answer(
        f"Сдано{late}. Можно заменить до проверки.",
        show_alert=True,
    )
    await manager.switch_to(StudentSG.assignment)


@inject
async def _clear(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    clear: FromDishka[ClearDraft],
) -> None:
    await clear(callback.from_user.id, remembered_id(manager, "assignment_id"))
    _ = await callback.answer("Черновик очищен.")


@inject
async def _file_received(
    message: Message,
    _widget: MessageInput,
    manager: DialogManager,
    add: FromDishka[AddFile],
) -> None:
    # An album arrives as several messages: keep only the newest window on screen.
    manager.show_mode = ShowMode.DELETE_AND_SEND
    if message.bot is None or message.from_user is None:
        return
    try:
        received = await receive(message.bot, message)
        if received is None:
            _ = await message.answer("Пришлите фото или файл.")
            return
        count = await add(
            message.from_user.id,
            remembered_id(manager, "assignment_id"),
            Upload(
                received.data,
                received.tg_file_id,
                received.tg_file_unique_id,
                received.sent_at,
            ),
        )
    except FileTooLargeError:
        _ = await message.answer(
            "Файл больше 20 МБ: сожмите его или разбейте на части.",
        )
        return
    except UnsupportedFileError:
        _ = await message.answer("Принимаются фото, PDF и DOCX. Этот файл не подходит.")
        return
    except TooManyFilesError:
        _ = await message.answer(
            "В черновике уже максимум файлов. Сдайте или очистите его.",
        )
        return
    except SubmissionClosedError:
        _ = await message.answer("Работа уже проверена, менять её нельзя.")
        return
    manager.dialog_data["draft_files"] = count


@inject
async def _upload_getter(
    dialog_manager: DialogManager,
    work: FromDishka[MyWork],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    state = await work(
        actor(dialog_manager),
        remembered_id(dialog_manager, "assignment_id"),
    )
    return {"count": state.draft_files, "can_submit": state.draft_files > 0}


@inject
async def _materials_getter(
    dialog_manager: DialogManager,
    published: FromDishka[PublishedMaterials],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    cards = await published(actor(dialog_manager), _group(dialog_manager))
    return {
        "cards": [(card.title, str(card.material_id)) for card in cards],
        "empty": not cards,
    }


@inject
async def _material_picked(
    callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
    files_of: FromDishka[MaterialFiles],
) -> None:
    card, files = await files_of(callback.from_user.id, uuid.UUID(item_id))
    for file in files:
        await send_file(
            callback.message,
            file.tg_file_id,
            file.kind,
            caption=safe(card.title) if file.position == 1 else None,
        )
    manager.show_mode = ShowMode.SEND


@inject
async def _scores_getter(
    dialog_manager: DialogManager,
    report: FromDishka[StudentReport],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    view = await report(actor(dialog_manager), _group(dialog_manager))
    score = view.score
    lines = [f"<b>Итого: {points(score.total)} из {points(score.cap_total)}</b>\n"]
    for part in score.parts:
        tail = "" if part.counted else " (пока не выставлялось)"
        lines.append(
            f"{safe(part.work_type.title)}: "
            f"{points(part.score)} из {points(part.work_type.cap)}{tail}",
        )
    if view.place is not None and view.buckets is not None:
        lines.extend((
            f"\nМесто в группе: {view.place} из {view.group_size}",
            "Распределение группы по итоговым баллам:",
        ))
        for bucket in reversed(view.buckets):
            count = "меньше 3" if bucket.count is None else str(bucket.count)
            lines.append(f"  {bucket.low_percent}–{bucket.high_percent}%: {count}")
    return {"text": "\n".join(lines)}


@inject
async def _settings_getter(
    dialog_manager: DialogManager,
    enabled: FromDishka[RemindersEnabled],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    on = await enabled(actor(dialog_manager))
    return {"reminders": "включены ✅" if on else "выключены ❌", "on": on}


@inject
async def _toggle_reminders(
    callback: CallbackQuery,
    _button: Button,
    _manager: DialogManager,
    enabled: FromDishka[RemindersEnabled],
    set_reminders: FromDishka[SetReminders],
) -> None:
    on = await enabled(callback.from_user.id)
    await set_reminders(callback.from_user.id, enabled=not on)


@inject
async def _my_data(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    memberships: FromDishka[Memberships],
    report: FromDishka[StudentReport],
    assignments: FromDishka[StudentAssignments],
) -> None:
    tg_user_id = callback.from_user.id
    export: list[dict[str, object]] = []
    for membership in await memberships(tg_user_id):
        group, student = membership.group, membership.student
        entry: dict[str, object] = {
            "group": group.name,
            "full_name": student.full_name,
            "binding": student.binding.value,
            "consent_version": student.consent_version,
            "consent_at": None
            if student.consent_at is None
            else student.consent_at.isoformat(),
        }
        if student.binding is BindingStatus.BOUND:
            view = await report(tg_user_id, group.group_id)
            entry["scores"] = {
                p.work_type.title: str(p.score) for p in view.score.parts
            }
            entry["homework"] = [
                {"title": w.assignment.title, "status": _status(w)}
                for w in await assignments(tg_user_id, group.group_id)
            ]
        export.append(entry)
    payload = json.dumps(
        {"telegram_id": tg_user_id, "groups": export},
        ensure_ascii=False,
        indent=2,
    )
    if callback.message is not None:
        _ = await callback.message.answer_document(
            BufferedInputFile(payload.encode(), filename="my_data.json"),
            caption="Всё, что бот хранит о вас.",
        )
    manager.show_mode = ShowMode.SEND


@inject
async def _forget(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    memberships: FromDishka[Memberships],
    files: FromDishka[DeleteStudentFiles],
    forget: FromDishka[ForgetAccount],
) -> None:
    rows = await memberships(callback.from_user.id)
    _ = await files([m.student.student_id for m in rows])
    _ = await forget(callback.from_user.id)
    _ = await callback.answer("Готово: привязка и файлы удалены.", show_alert=True)
    await manager.done()


student_dialog = Dialog(
    Window(
        Const("Выберите группу:"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="group",
                item_id_getter=itemgetter(1),
                items="groups",
                on_click=_group_picked,
            ),
            id="groups",
            width=1,
            height=6,
        ),
        getter=_groups_getter,
        state=StudentSG.groups,
    ),
    Window(
        Format("<b>{name}</b>\n{group}"),
        Row(
            SwitchTo(Const("📝 Домашки"), id="hw", state=StudentSG.homework),
            SwitchTo(Const("📚 Семинары"), id="mat", state=StudentSG.materials),
        ),
        Row(
            SwitchTo(Const("📊 Мои баллы"), id="sc", state=StudentSG.scores),
            SwitchTo(Const("⚙️ Настройки"), id="set", state=StudentSG.settings),
        ),
        SwitchTo(
            Const("🔁 Другая группа"),
            id="other",
            state=StudentSG.groups,
            when="several",
        ),
        getter=_menu_getter,
        state=StudentSG.menu,
    ),
    Window(
        Const("Домашние задания:"),
        Const("Пока заданий нет.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="work",
                item_id_getter=itemgetter(1),
                items="works",
                on_click=_assignment_picked,
            ),
            id="works",
            width=1,
            height=6,
        ),
        SwitchTo(Const("« Меню"), id="back", state=StudentSG.menu),
        getter=_homework_getter,
        state=StudentSG.homework,
    ),
    Window(
        Format("{text}"),
        Button(
            Const("📄 Условие"),
            id="statement",
            on_click=_send_statement,
            when="has_statement",
        ),
        SwitchTo(
            Const("📎 Добавить файлы"),
            id="add",
            state=StudentSG.upload,
            when="can_add",
        ),
        Row(
            Button(Const("✅ Сдать"), id="submit", on_click=_submit, when="can_submit"),
            Button(
                Const("🗑 Очистить черновик"),
                id="clear",
                on_click=_clear,
                when="can_submit",
            ),
        ),
        SwitchTo(Const("« Задания"), id="back", state=StudentSG.homework),
        getter=_assignment_getter,
        state=StudentSG.assignment,
    ),
    Window(
        Format(
            "Пришлите фото или файлы (PDF, DOCX), можно альбомом.\n"
            "В черновике сейчас: {count}. Когда всё готово — «Сдать».",
        ),
        MessageInput(
            _file_received,
            content_types=[ContentType.PHOTO, ContentType.DOCUMENT],
        ),
        Button(Const("✅ Сдать"), id="submit", on_click=_submit, when="can_submit"),
        SwitchTo(Const("« Назад"), id="back", state=StudentSG.assignment),
        getter=_upload_getter,
        state=StudentSG.upload,
    ),
    Window(
        Const("Семинары — нажмите, чтобы получить файлы:"),
        Const("Пока ничего не опубликовано.", when="empty"),
        ScrollingGroup(
            Select(
                Format("📄 {item[0]}"),
                id="card",
                item_id_getter=itemgetter(1),
                items="cards",
                # dishka's inject types the widget as ManagedWidget, Select wants itself
                on_click=_material_picked,  # pyright: ignore[reportArgumentType]
            ),
            id="cards",
            width=1,
            height=6,
        ),
        SwitchTo(Const("« Меню"), id="back", state=StudentSG.menu),
        getter=_materials_getter,
        state=StudentSG.materials,
    ),
    Window(
        Format("{text}"),
        SwitchTo(Const("« Меню"), id="back", state=StudentSG.menu),
        getter=_scores_getter,
        state=StudentSG.scores,
    ),
    Window(
        Format("Напоминания о дедлайнах: {reminders}"),
        Button(
            Const("🔔 Переключить напоминания"),
            id="toggle",
            on_click=_toggle_reminders,
        ),
        Button(Const("📦 Мои данные"), id="data", on_click=_my_data),
        SwitchTo(Const("🗑 Удалить мои данные"), id="forget", state=StudentSG.forget),
        SwitchTo(Const("« Меню"), id="back", state=StudentSG.menu),
        getter=_settings_getter,
        state=StudentSG.settings,
    ),
    Window(
        Const(
            "Удалить привязку Telegram ко всем вашим группам и все сданные файлы?\n"
            "Баллы останутся в ведомости преподавателя. Это нельзя отменить.",
        ),
        Button(Const("Да, удалить"), id="yes", on_click=_forget),
        Button(Const("Нет"), id="no", on_click=go(StudentSG.settings)),
        state=StudentSG.forget,
    ),
)
