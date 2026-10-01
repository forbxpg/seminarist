"""The teacher's push buttons: approve or reject a claimed name."""

from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery
from dishka.integrations.aiogram import FromDishka

from smr.bot.texts import safe
from smr.core.database import UnitOfWork
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.roster.application.contracts import RosterApi
from smr.roster.application.use_cases import ApproveBinding, RejectBinding
from smr.roster.domain import NotPendingError, StudentNotFoundError

router = Router(name="bindings")


@router.callback_query(F.data.startswith("bind:"))
async def decide(
    callback: CallbackQuery,
    *,
    is_admin: bool,
    approve: FromDishka[ApproveBinding],
    reject: FromDishka[RejectBinding],
    roster: FromDishka[RosterApi],
    notifications: FromDishka[NotificationsApi],
    uow: FromDishka[UnitOfWork],
) -> None:
    """Approve or reject, then tell the student."""
    if not is_admin or callback.data is None:
        _ = await callback.answer("Только для преподавателя.", show_alert=True)
        return
    _, verdict, raw_id = callback.data.split(":", 2)
    student_id = uuid.UUID(raw_id)
    try:
        if verdict == "approve":
            student = await approve(callback.from_user.id, student_id)
        else:
            student = await reject(callback.from_user.id, student_id)
    except (NotPendingError, StudentNotFoundError):
        _ = await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    group = await roster.group(student.group_id)
    title = "" if group is None else group.title
    if student.tg_user_id is not None:
        kind = (
            NotificationKind.BINDING_APPROVED
            if verdict == "approve"
            else NotificationKind.BINDING_REJECTED
        )
        async with uow:
            await notifications.notify_account(
                student.tg_user_id,
                kind,
                {"group": title},
            )
            await uow.commit()
    mark = "✅ подтверждён(а)" if verdict == "approve" else "❌ отклонён(а)"
    if callback.message is not None:
        _ = await callback.message.edit_text(f"{safe(student.full_name)} — {mark}")  # pyright: ignore[reportAttributeAccessIssue]
    _ = await callback.answer()
