"""`/start` (with or without a group link) and `/admin`."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from dishka.integrations.aiogram import FromDishka

from smr.bot.states import AdminSG, JoinSG, StudentSG
from smr.roster.application.use_cases import Memberships, ResolveInvite
from smr.roster.domain import BindingStatus, GroupArchivedError, InviteNotFoundError

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def start_with_link(
    message: Message,
    command: CommandObject,
    dialog_manager: DialogManager,
    resolve: FromDishka[ResolveInvite],
) -> None:
    """A student opened a group's link: check it and start joining."""
    code = command.args or ""
    try:
        _ = await resolve(code)
    except InviteNotFoundError:
        _ = await message.answer(
            "Ссылка устарела или неверна. Попросите новую у преподавателя.",
        )
        return
    except GroupArchivedError:
        _ = await message.answer("Эта группа уже в архиве.")
        return
    await dialog_manager.start(
        JoinSG.consent,
        data={"invite": code},
        mode=StartMode.RESET_STACK,
    )


@router.message(CommandStart())
async def start(
    message: Message,
    dialog_manager: DialogManager,
    memberships: FromDishka[Memberships],
    *,
    is_admin: bool,
) -> None:
    """Open the teacher's menu, the menu of a bound student, or say what is missing."""
    if message.from_user is None:
        return
    if is_admin:
        await dialog_manager.start(AdminSG.menu, mode=StartMode.RESET_STACK)
        return
    rows = await memberships(message.from_user.id)
    bound = [m for m in rows if m.student.binding is BindingStatus.BOUND]
    if len(bound) == 1:
        await dialog_manager.start(
            StudentSG.menu,
            data={"group_id": str(bound[0].group.group_id)},
            mode=StartMode.RESET_STACK,
        )
    elif bound:
        await dialog_manager.start(StudentSG.groups, mode=StartMode.RESET_STACK)
    elif rows:
        _ = await message.answer("⏳ Ваша заявка ждёт подтверждения преподавателя.")
    else:
        _ = await message.answer(
            "Привет! Чтобы войти, откройте ссылку своей группы — "
            "её даёт преподаватель.",
        )


@router.message(Command("admin"), F.from_user.func(lambda user: user is not None))
async def admin(
    message: Message,
    dialog_manager: DialogManager,
    *,
    is_admin: bool,
) -> None:
    """Open the teacher's menu."""
    if not is_admin:
        _ = await message.answer("Эта команда только для преподавателя.")
        return
    await dialog_manager.start(AdminSG.menu, mode=StartMode.RESET_STACK)
