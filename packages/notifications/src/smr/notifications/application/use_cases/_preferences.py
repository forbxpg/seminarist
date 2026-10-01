"""A student turns reminders on or off, for all their groups at once."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from smr.roster.domain import BindingStatus

if TYPE_CHECKING:
    from smr.core.database import UnitOfWork
    from smr.notifications.application.ports import Preferences
    from smr.roster.application.use_cases import Memberships


@final
class SetReminders:
    """Reminders on or off for every bound row of an account."""

    def __init__(
        self,
        memberships: Memberships,
        preferences: Preferences,
        uow: UnitOfWork,
    ) -> None:
        self._memberships: Memberships = memberships
        self._preferences: Preferences = preferences
        self._uow: UnitOfWork = uow

    async def __call__(self, tg_user_id: int, *, enabled: bool) -> None:
        """Store it.

        Args:
            tg_user_id: int - The account.
            enabled: bool - On or off.

        """
        rows = [
            m.student.student_id
            for m in await self._memberships(tg_user_id)
            if m.student.binding is BindingStatus.BOUND
        ]
        async with self._uow:
            await self._preferences.set_reminders(rows, enabled=enabled)
            await self._uow.commit()


@final
class RemindersEnabled:
    """Whether an account gets reminders."""

    def __init__(self, memberships: Memberships, preferences: Preferences) -> None:
        self._memberships: Memberships = memberships
        self._preferences: Preferences = preferences

    async def __call__(self, tg_user_id: int) -> bool:
        """Tell it.

        Args:
            tg_user_id: int - The account.

        Returns:
            bool - True unless every bound row has reminders off.

        """
        rows = [m.student.student_id for m in await self._memberships(tg_user_id)]
        if not rows:
            return True
        return len(await self._preferences.muted(rows)) < len(rows)
