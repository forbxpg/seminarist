"""A notice waiting in the outbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._kinds import NotificationKind


@dataclass(frozen=True, slots=True)
class Notice:
    """A notice to one Telegram account.

    Attributes:
        notice_id: int - The notice.
        tg_user_id: int - Whom to tell.
        kind: NotificationKind - What about.
        payload: Mapping[str, object] - The values its text needs.
        attempts: int - Deliveries tried so far.

    """

    notice_id: int
    tg_user_id: int
    kind: NotificationKind
    payload: Mapping[str, object]
    attempts: int
