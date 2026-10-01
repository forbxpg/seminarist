"""The teacher's menu: groups, their rosters, links, settings; requests; backup."""

from __future__ import annotations

import dataclasses
import uuid
from operator import itemgetter
from typing import Any

from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import (
    Button,
    ListGroup,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format
from dishka.integrations.aiogram_dialog import FromDishka, inject

from smr.bot.dialogs.common import actor, go, remembered_id, start_with
from smr.bot.exports import write_sheet
from smr.bot.states import AdminSG, GradebookSG, HomeworkSG, MaterialsSG, SessionsSG
from smr.bot.texts import safe
from smr.core.backup import Backup, BackupError
from smr.core.clock import Clock
from smr.core.config import StorageSettings
from smr.core.database import UnitOfWork
from smr.gradebook.application.use_cases import GroupSheet
from smr.homework.application.use_cases import DeleteStudentFiles
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.roster.application.contracts import RosterApi
from smr.roster.application.use_cases import (
    ApproveBinding,
    ArchiveGroup,
    CreateGroup,
    ImportRoster,
    ListGroups,
    ListStudents,
    PendingBindings,
    RejectBinding,
    RemoveStudent,
    RotateInvite,
    Unbind,
    UpdateGroupSettings,
)
from smr.roster.domain import BindingStatus, NotPendingError

_MIDDLEWARE = Any
_MARK = {
    BindingStatus.BOUND: "✅",
    BindingStatus.PENDING: "⏳",
    BindingStatus.UNBOUND: "▫️",
}

_SETTINGS: dict[str, tuple[str, type]] = {
    "reminder_hours": ("За сколько часов до дедлайна напоминать (1–168)", int),
    "board_weight": (
        "Насколько выходы к доске снижают шанс (0 и больше, обычно 1)",
        float,
    ),
    "score_weight": (
        "Насколько высокий балл снижает шанс (0 и больше, обычно 1)",
        float,
    ),
    "retention_days": ("Сколько дней хранить данные группы после архива", int),
}


def _group(manager: DialogManager) -> uuid.UUID:
    return remembered_id(manager, "group_id")


@inject
async def _menu_getter(
    dialog_manager: DialogManager,
    pending: FromDishka[PendingBindings],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    return {"pending": len(await pending(actor(dialog_manager)))}


@inject
async def _backup(
    callback: CallbackQuery,
    _button: Button,
    _manager: DialogManager,
    backup: FromDishka[Backup],
) -> None:
    _ = await callback.answer("Делаю бэкап…")
    try:
        target = await backup()
    except BackupError:
        if callback.message is not None:
            _ = await callback.message.answer(
                "❌ Бэкап не удался, подробности в логах.",
            )
        return
    if callback.message is not None:
        _ = await callback.message.answer(f"💾 Бэкап готов: {safe(target.name)}")


@inject
async def _groups_getter(
    dialog_manager: DialogManager,
    groups: FromDishka[ListGroups],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    found = await groups(actor(dialog_manager), include_archived=True)
    return {
        "groups": [
            (("" if g.is_active else "🗄 ") + g.name, str(g.group_id)) for g in found
        ],
    }


async def _group_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["group_id"] = item_id
    await manager.switch_to(AdminSG.group)


async def _remember(
    _message: Message,
    widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
) -> None:
    key = str(widget.widget_id)
    manager.dialog_data[key] = value
    next_state = {"title": AdminSG.new_subject, "subject": AdminSG.new_semester}
    await manager.switch_to(next_state[key])


@inject
async def _create_group(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    create: FromDishka[CreateGroup],
) -> None:
    if message.from_user is None:
        return
    group = await create(
        message.from_user.id,
        title=str(manager.dialog_data["title"]),
        subject=str(manager.dialog_data["subject"]),
        semester=value,
    )
    manager.dialog_data["group_id"] = str(group.group_id)
    await manager.switch_to(AdminSG.group)


@inject
async def _group_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    group = await roster.group(_group(dialog_manager))
    students = await roster.students_of(_group(dialog_manager))
    bound = sum(1 for s in students if s.binding is BindingStatus.BOUND)
    return {
        "name": safe("" if group is None else group.name),
        "size": len(students),
        "bound": bound,
        "active": group is not None and group.is_active,
    }


@inject
async def _export(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    sheet: FromDishka[GroupSheet],
    roster: FromDishka[RosterApi],
    storage: FromDishka[StorageSettings],
    clock: FromDishka[Clock],
) -> None:
    group = await roster.group(_group(manager))
    if group is None:
        return
    rows = await sheet(callback.from_user.id, group.group_id)
    target = write_sheet(group, rows, storage.data_dir / "exports", clock.now())
    if callback.message is not None:
        _ = await callback.message.answer_document(
            FSInputFile(target),
            caption="Ведомость (копия лежит в data/exports).",
        )
    manager.show_mode = ShowMode.SEND


@inject
async def _roster_getter(
    dialog_manager: DialogManager,
    students: FromDishka[ListStudents],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await students(actor(dialog_manager), _group(dialog_manager))
    return {
        "students": [
            (f"{_MARK[s.binding]} {s.full_name}", str(s.student_id)) for s in rows
        ],
        "empty": not rows,
    }


@inject
async def _import(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    importer: FromDishka[ImportRoster],
) -> None:
    if message.from_user is None:
        return
    result = await importer(message.from_user.id, _group(manager), value)
    _ = await message.answer(f"Добавлено: {result.added}, уже были: {result.skipped}.")
    await manager.switch_to(AdminSG.roster)


async def _student_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["student_id"] = item_id
    await manager.switch_to(AdminSG.student)


@inject
async def _student_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    student = await roster.student(remembered_id(dialog_manager, "student_id"))
    if student is None:
        return {"name": "—", "status": "удалён", "bound": False}
    status = {
        BindingStatus.BOUND: "привязан к Telegram",
        BindingStatus.PENDING: "ждёт подтверждения",
        BindingStatus.UNBOUND: "не привязан",
    }[student.binding]
    return {
        "name": safe(student.full_name),
        "status": status,
        "bound": student.binding is not BindingStatus.UNBOUND,
    }


@inject
async def _unbind(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    unbind: FromDishka[Unbind],
) -> None:
    _ = await unbind(callback.from_user.id, remembered_id(manager, "student_id"))
    _ = await callback.answer("Отвязан.")


@inject
async def _remove(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    files: FromDishka[DeleteStudentFiles],
    remove: FromDishka[RemoveStudent],
) -> None:
    student_id = remembered_id(manager, "student_id")
    _ = await files([student_id])
    _ = await remove(callback.from_user.id, student_id)
    _ = await callback.answer(
        "Удалён из списка вместе с баллами и файлами.",
        show_alert=True,
    )
    await manager.switch_to(AdminSG.roster)


@inject
async def _invite_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **kwargs: _MIDDLEWARE,
) -> dict[str, object]:
    group = await roster.group(_group(dialog_manager))
    bot = kwargs.get("bot") or dialog_manager.middleware_data.get("bot")
    me = await bot.me() if bot is not None else None
    username = "" if me is None else me.username
    code = "" if group is None else group.invite_code
    return {"link": f"https://t.me/{username}?start={code}"}


@inject
async def _rotate(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    rotate: FromDishka[RotateInvite],
) -> None:
    _ = await rotate(callback.from_user.id, _group(manager))
    _ = await callback.answer("Старая ссылка больше не работает.", show_alert=True)


@inject
async def _settings_getter(
    dialog_manager: DialogManager,
    roster: FromDishka[RosterApi],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    group = await roster.group(_group(dialog_manager))
    if group is None:
        return {"text": "Группа не найдена"}
    s = group.settings
    return {
        "text": (
            f"Напоминать за: {s.reminder_hours} ч\n"
            f"Вес выходов к доске: {s.board_weight}\n"
            f"Вес баллов: {s.score_weight}\n"
            f"Хранить после архива: {s.retention_days} дн.\n"
            f"Место в группе студентам: {'показывать' if s.show_rank else 'скрывать'}"
        ),
        "settings": [
            (label.split(" (")[0], key) for key, (label, _kind) in _SETTINGS.items()
        ],
    }


async def _setting_picked(
    _callback: CallbackQuery,
    _widget: object,
    manager: DialogManager,
    item_id: str,
) -> None:
    manager.dialog_data["setting"] = item_id
    await manager.switch_to(AdminSG.setting_value)


async def _setting_prompt(
    dialog_manager: DialogManager,
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    key = str(dialog_manager.dialog_data.get("setting", ""))
    return {"prompt": _SETTINGS[key][0] if key in _SETTINGS else ""}


@inject
async def _setting_saved(
    message: Message,
    _widget: ManagedTextInput[str],
    manager: DialogManager,
    value: str,
    roster: FromDishka[RosterApi],
    update: FromDishka[UpdateGroupSettings],
) -> None:
    group = await roster.group(_group(manager))
    key = str(manager.dialog_data["setting"])
    if group is None or message.from_user is None:
        return
    kind = _SETTINGS[key][1]
    try:
        parsed = kind(value.replace(",", "."))
    except ValueError:
        _ = await message.answer("Нужно число.")
        return
    changed = dataclasses.replace(group.settings, **{key: parsed})
    _ = await update(message.from_user.id, group.group_id, changed)
    await manager.switch_to(AdminSG.settings)


@inject
async def _toggle_rank(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    roster: FromDishka[RosterApi],
    update: FromDishka[UpdateGroupSettings],
) -> None:
    group = await roster.group(_group(manager))
    if group is None:
        return
    changed = dataclasses.replace(
        group.settings,
        show_rank=not group.settings.show_rank,
    )
    _ = await update(callback.from_user.id, group.group_id, changed)


@inject
async def _archive(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    archive: FromDishka[ArchiveGroup],
) -> None:
    await archive(callback.from_user.id, _group(manager))
    _ = await callback.answer("Группа в архиве.", show_alert=True)
    await manager.switch_to(AdminSG.groups)


@inject
async def _pending_getter(
    dialog_manager: DialogManager,
    pending: FromDishka[PendingBindings],
    **_: _MIDDLEWARE,
) -> dict[str, object]:
    rows = await pending(actor(dialog_manager))
    return {
        "requests": [
            (f"{m.student.full_name} · {m.group.title}", str(m.student.student_id))
            for m in rows
        ],
        "empty": not rows,
    }


async def _decide(
    callback: CallbackQuery,
    manager: DialogManager,
    decide: ApproveBinding | RejectBinding,
    roster: RosterApi,
    notifications: NotificationsApi,
    uow: UnitOfWork,
) -> None:
    item_id: object = getattr(manager, "item_id", None)
    approve = isinstance(decide, ApproveBinding)
    try:
        student = await decide(callback.from_user.id, uuid.UUID(str(item_id)))
    except NotPendingError:
        _ = await callback.answer("Уже обработано.")
        return
    group = await roster.group(student.group_id)
    if student.tg_user_id is not None:
        kind = (
            NotificationKind.BINDING_APPROVED
            if approve
            else NotificationKind.BINDING_REJECTED
        )
        async with uow:
            await notifications.notify_account(
                student.tg_user_id,
                kind,
                {"group": "" if group is None else group.title},
            )
            await uow.commit()
    _ = await callback.answer("Подтверждён(а)." if approve else "Отклонено.")


@inject
async def _approve(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    approve: FromDishka[ApproveBinding],
    roster: FromDishka[RosterApi],
    notifications: FromDishka[NotificationsApi],
    uow: FromDishka[UnitOfWork],
) -> None:
    await _decide(callback, manager, approve, roster, notifications, uow)


@inject
async def _reject(
    callback: CallbackQuery,
    _button: Button,
    manager: DialogManager,
    reject: FromDishka[RejectBinding],
    roster: FromDishka[RosterApi],
    notifications: FromDishka[NotificationsApi],
    uow: FromDishka[UnitOfWork],
) -> None:
    await _decide(callback, manager, reject, roster, notifications, uow)


groups_dialog = Dialog(
    Window(
        Const("👩‍🏫 Меню преподавателя"),
        SwitchTo(Const("🎓 Группы"), id="groups", state=AdminSG.groups),
        SwitchTo(Format("🙋 Заявки ({pending})"), id="pending", state=AdminSG.pending),
        Button(Const("💾 Бэкап сейчас"), id="backup", on_click=_backup),
        getter=_menu_getter,
        state=AdminSG.menu,
    ),
    Window(
        Const("Группы:"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="group",
                item_id_getter=itemgetter(1),
                items="groups",
                on_click=_group_picked,
            ),
            id="groups_list",
            width=1,
            height=8,
        ),
        SwitchTo(Const("➕ Новая группа"), id="new", state=AdminSG.new_title),
        SwitchTo(Const("« Меню"), id="back", state=AdminSG.menu),
        getter=_groups_getter,
        state=AdminSG.groups,
    ),
    Window(
        Const("Название группы, например К01-261:"),
        TextInput(id="title", on_success=_remember),
        SwitchTo(Const("Отмена"), id="cancel", state=AdminSG.groups),
        state=AdminSG.new_title,
    ),
    Window(
        Const("Предмет, например «Дискретная математика»:"),
        TextInput(id="subject", on_success=_remember),
        SwitchTo(Const("Отмена"), id="cancel", state=AdminSG.groups),
        state=AdminSG.new_subject,
    ),
    Window(
        Const("Семестр, например «осень 2026»:"),
        TextInput(id="semester", on_success=_create_group),
        SwitchTo(Const("Отмена"), id="cancel", state=AdminSG.groups),
        state=AdminSG.new_semester,
    ),
    Window(
        Format("<b>{name}</b>\nВ списке: {size}, привязано: {bound}"),
        Row(
            SwitchTo(Const("👥 Список"), id="roster", state=AdminSG.roster),
            SwitchTo(Const("🔗 Ссылка"), id="invite", state=AdminSG.invite),
        ),
        Row(
            Button(
                Const("🗓 Занятия"),
                id="sessions",
                on_click=start_with(SessionsSG.list, "group_id"),
            ),
            Button(
                Const("📝 ДЗ"),
                id="homework",
                on_click=start_with(HomeworkSG.list, "group_id"),
            ),
        ),
        Row(
            Button(
                Const("📚 Семинары"),
                id="materials",
                on_click=start_with(MaterialsSG.list, "group_id"),
            ),
            Button(
                Const("📊 Баллы"),
                id="gradebook",
                on_click=start_with(GradebookSG.types, "group_id"),
            ),
        ),
        Button(Const("📥 Ведомость XLSX"), id="export", on_click=_export),
        Row(
            SwitchTo(Const("⚙️ Настройки"), id="settings", state=AdminSG.settings),
            SwitchTo(
                Const("🗄 В архив"),
                id="archive",
                state=AdminSG.archive,
                when="active",
            ),
        ),
        SwitchTo(Const("« Группы"), id="back", state=AdminSG.groups),
        getter=_group_getter,
        state=AdminSG.group,
    ),
    Window(
        Const("Список группы (✅ привязан, ⏳ ждёт, ▫️ нет):"),
        Const("Список пуст — добавьте ФИО.", when="empty"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="student",
                item_id_getter=itemgetter(1),
                items="students",
                on_click=_student_picked,
            ),
            id="students_list",
            width=1,
            height=10,
        ),
        SwitchTo(Const("➕ Добавить ФИО"), id="paste", state=AdminSG.roster_paste),
        SwitchTo(Const("« Группа"), id="back", state=AdminSG.group),
        getter=_roster_getter,
        state=AdminSG.roster,
    ),
    Window(
        Const("Вставьте ФИО столбиком, по одному в строке (нумерация не мешает):"),
        TextInput(id="paste", on_success=_import),
        SwitchTo(Const("Отмена"), id="cancel", state=AdminSG.roster),
        state=AdminSG.roster_paste,
    ),
    Window(
        Format("<b>{name}</b>\n{status}"),
        Button(
            Const("🔓 Отвязать Telegram"),
            id="unbind",
            on_click=_unbind,
            when="bound",
        ),
        Button(Const("🗑 Удалить из списка"), id="remove", on_click=_remove),
        SwitchTo(Const("« Список"), id="back", state=AdminSG.roster),
        getter=_student_getter,
        state=AdminSG.student,
    ),
    Window(
        Format("Ссылка для группы (отправьте студентам):\n{link}"),
        Button(Const("🔄 Новая ссылка"), id="rotate", on_click=_rotate),
        SwitchTo(Const("« Группа"), id="back", state=AdminSG.group),
        getter=_invite_getter,
        state=AdminSG.invite,
    ),
    Window(
        Format("{text}"),
        ScrollingGroup(
            Select(
                Format("✏️ {item[0]}"),
                id="setting",
                item_id_getter=itemgetter(1),
                items="settings",
                on_click=_setting_picked,
            ),
            id="settings_list",
            width=1,
            height=6,
        ),
        Button(Const("👁 Показывать/скрывать место"), id="rank", on_click=_toggle_rank),
        SwitchTo(Const("« Группа"), id="back", state=AdminSG.group),
        getter=_settings_getter,
        state=AdminSG.settings,
    ),
    Window(
        Format("{prompt}"),
        TextInput(id="value", on_success=_setting_saved),
        SwitchTo(Const("Отмена"), id="cancel", state=AdminSG.settings),
        getter=_setting_prompt,
        state=AdminSG.setting_value,
    ),
    Window(
        Const(
            "Отправить группу в архив? Она станет только для чтения, "
            "а через срок хранения данные удалятся.",
        ),
        Button(Const("Да, в архив"), id="yes", on_click=_archive),
        Button(Const("Нет"), id="no", on_click=go(AdminSG.group)),
        state=AdminSG.archive,
    ),
    Window(
        Const("Заявки на привязку:"),
        Const("Заявок нет.", when="empty"),
        ListGroup(
            Row(
                Button(Format("✅ {item[0]}"), id="approve", on_click=_approve),
                Button(Const("❌"), id="reject", on_click=_reject),
            ),
            id="requests_list",
            item_id_getter=itemgetter(1),
            items="requests",
        ),
        SwitchTo(Const("« Меню"), id="back", state=AdminSG.menu),
        getter=_pending_getter,
        state=AdminSG.pending,
    ),
)
