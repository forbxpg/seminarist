"""The outbox and the preferences over the SQLAlchemy session."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from smr.notifications.domain import Notice, NotificationKind
from smr.notifications.infrastructure.models import (
    OUTBOX_DEDUPE_UNIQUE,
    OutboxModel,
    PreferenceModel,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Collection, Mapping, Sequence
    from datetime import datetime

    from sqlalchemy import CursorResult
    from sqlalchemy.ext.asyncio import AsyncSession


@final
class SqlAlchemyOutbox:
    """`Outbox` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(
        self,
        tg_user_id: int,
        kind: NotificationKind,
        payload: Mapping[str, object],
        dedupe_key: str | None,
    ) -> bool:
        """Queue a notice; one with a dedupe key already queued is skipped.

        Args:
            tg_user_id: int - Whom to tell.
            kind: NotificationKind - What about.
            payload: Mapping[str, object] - The values of its text.
            dedupe_key: str | None - What makes a repeat a repeat.

        Returns:
            bool - False when it was a repeat and nothing was queued.

        """
        queued = await self._session.scalar(
            insert(OutboxModel)
            .values(
                tg_user_id=tg_user_id,
                kind=kind.value,
                payload=dict(payload),
                dedupe_key=dedupe_key,
            )
            .on_conflict_do_nothing(constraint=OUTBOX_DEDUPE_UNIQUE)
            .returning(OutboxModel.id),
        )
        return queued is not None

    async def pending(self, limit: int) -> Sequence[Notice]:
        """Take the oldest notices to send, locked against other workers.

        Args:
            limit: int - How many.

        Returns:
            Sequence[Notice] - The notices.

        """
        rows = await self._session.scalars(
            select(OutboxModel)
            .where(OutboxModel.sent_at.is_(None), OutboxModel.gave_up.is_(False))
            .order_by(OutboxModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True),
        )
        return [
            Notice(
                notice_id=row.id,
                tg_user_id=row.tg_user_id,
                kind=NotificationKind(row.kind),
                payload=row.payload,
                attempts=row.attempts,
            )
            for row in rows
        ]

    async def sent(self, notice_id: int, now: datetime) -> None:
        """Mark a notice sent.

        Args:
            notice_id: int - The notice.
            now: datetime - When.

        """
        _ = await self._session.execute(
            update(OutboxModel)
            .where(OutboxModel.id == notice_id)
            .values(sent_at=now, attempts=OutboxModel.attempts + 1),
        )

    async def failed(self, notice_id: int, error: str, *, give_up: bool) -> None:
        """Count a failed delivery.

        Args:
            notice_id: int - The notice.
            error: str - What went wrong, without personal data.
            give_up: bool - Never try this notice again.

        """
        _ = await self._session.execute(
            update(OutboxModel)
            .where(OutboxModel.id == notice_id)
            .values(
                attempts=OutboxModel.attempts + 1,
                last_error=error,
                gave_up=give_up,
            ),
        )

    async def purge(self, before: datetime) -> int:
        """Delete sent or abandoned notices created before a moment.

        Args:
            before: datetime - The moment.

        Returns:
            int - How many were deleted.

        """
        deleted = await self._session.execute(
            delete(OutboxModel).where(
                OutboxModel.created_at < before,
                or_(OutboxModel.sent_at.is_not(None), OutboxModel.gave_up.is_(True)),
            ),
        )
        # DML returns a CursorResult, which has `rowcount`.
        return cast("CursorResult[object]", deleted).rowcount


@final
class SqlAlchemyPreferences:
    """`Preferences` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def set_reminders(
        self,
        student_ids: Collection[uuid.UUID],
        *,
        enabled: bool,
    ) -> None:
        """Turn reminders on or off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.
            enabled: bool - On or off.

        """
        if not student_ids:
            return
        statement = insert(PreferenceModel).values(
            [{"student_id": sid, "reminders": enabled} for sid in student_ids],
        )
        _ = await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[PreferenceModel.student_id],
                set_={"reminders": statement.excluded.reminders},
            ),
        )

    async def muted(self, student_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        """Tell which of the students turned reminders off.

        Args:
            student_ids: Collection[uuid.UUID] - The students.

        Returns:
            set[uuid.UUID] - Those with reminders off.

        """
        if not student_ids:
            return set()
        rows = await self._session.scalars(
            select(PreferenceModel.student_id).where(
                PreferenceModel.student_id.in_(student_ids),
                PreferenceModel.reminders.is_(False),
            ),
        )
        return set(rows)
