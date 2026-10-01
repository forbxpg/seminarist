"""The teachers' guard."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Collection


class NotAdminError(Exception):
    """The Telegram account is not one of the teachers."""


@final
class AdminGuard:
    """Tells the teachers apart by their Telegram ids."""

    def __init__(self, admin_ids: Collection[int]) -> None:
        self._admin_ids: frozenset[int] = frozenset(admin_ids)

    @property
    def admin_ids(self) -> frozenset[int]:
        """Tell the teachers' ids.

        Returns:
            frozenset[int] - Their Telegram user ids.

        """
        return self._admin_ids

    def is_admin(self, tg_user_id: int) -> bool:
        """Tell whether an account is a teacher's.

        Args:
            tg_user_id: int - Telegram user id.

        Returns:
            bool - True for a teacher.

        """
        return tg_user_id in self._admin_ids

    def require(self, tg_user_id: int) -> None:
        """Let only a teacher through.

        Args:
            tg_user_id: int - Telegram user id.

        Raises:
            NotAdminError: If the account is not a teacher's.

        """
        if not self.is_admin(tg_user_id):
            raise NotAdminError
