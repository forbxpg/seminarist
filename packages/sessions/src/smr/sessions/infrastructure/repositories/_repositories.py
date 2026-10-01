"""Sessions, attendance and board calls over the SQLAlchemy session."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from smr.sessions.domain import AttendanceStatus, BoardCall, BoardMode, Session
from smr.sessions.infrastructure.models import (
    AttendanceModel,
    BoardCallModel,
    SessionModel,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


@final
class SqlAlchemySessions:
    """`SessionRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, session: Session) -> None:
        """Add a session.

        Args:
            session: Session - It.

        """
        self._session.add(
            SessionModel(
                id=session.session_id,
                group_id=session.group_id,
                starts_at=session.starts_at,
                topic=session.topic,
                attendance_item_id=session.attendance_item_id,
            ),
        )
        await self._session.flush()

    async def get(self, session_id: uuid.UUID) -> Session | None:
        """Read a session.

        Args:
            session_id: uuid.UUID - It.

        Returns:
            Session | None - It, or None.

        """
        row = await self._session.get(SessionModel, session_id, populate_existing=True)
        return None if row is None else _session(row)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Session]:
        """List a group's sessions, the latest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Session] - Its sessions.

        """
        rows = await self._session.scalars(
            select(SessionModel)
            .where(SessionModel.group_id == group_id)
            .order_by(SessionModel.starts_at.desc()),
        )
        return [_session(row) for row in rows]

    async def set_attendance_item(
        self,
        session_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        """Tie a session to its attendance item in the ledger.

        Args:
            session_id: uuid.UUID - The session.
            item_id: uuid.UUID - The item.

        """
        _ = await self._session.execute(
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(attendance_item_id=item_id),
        )

    async def delete(self, session_id: uuid.UUID) -> None:
        """Delete a session with its attendance and calls.

        Args:
            session_id: uuid.UUID - It.

        """
        _ = await self._session.execute(
            delete(SessionModel).where(SessionModel.id == session_id),
        )


@final
class SqlAlchemyAttendance:
    """`AttendanceRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def of_session(
        self,
        session_id: uuid.UUID,
    ) -> dict[uuid.UUID, AttendanceStatus]:
        """Read a session's attendance.

        Args:
            session_id: uuid.UUID - The session.

        Returns:
            dict[uuid.UUID, AttendanceStatus] - Each marked student's status.

        """
        rows = await self._session.scalars(
            select(AttendanceModel).where(AttendanceModel.session_id == session_id),
        )
        return {row.student_id: AttendanceStatus(row.status) for row in rows}

    async def save(
        self,
        session_id: uuid.UUID,
        statuses: Mapping[uuid.UUID, AttendanceStatus],
    ) -> None:
        """Store statuses, replacing those already marked.

        Args:
            session_id: uuid.UUID - The session.
            statuses: Mapping[uuid.UUID, AttendanceStatus] - Each student's status.

        """
        if not statuses:
            return
        statement = insert(AttendanceModel).values(
            [
                {"session_id": session_id, "student_id": sid, "status": status.value}
                for sid, status in statuses.items()
            ],
        )
        _ = await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[AttendanceModel.session_id, AttendanceModel.student_id],
                set_={"status": statement.excluded.status},
            ),
        )


@final
class SqlAlchemyBoardCalls:
    """`BoardCallRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, call: BoardCall) -> None:
        """Add a call.

        Args:
            call: BoardCall - It.

        """
        self._session.add(
            BoardCallModel(
                id=call.call_id,
                session_id=call.session_id,
                student_id=call.student_id,
                mode=call.mode.value,
                task=call.task,
                entry_id=call.entry_id,
                called_at=call.called_at,
            ),
        )
        await self._session.flush()

    async def get(self, call_id: uuid.UUID) -> BoardCall | None:
        """Read a call.

        Args:
            call_id: uuid.UUID - It.

        Returns:
            BoardCall | None - It, or None.

        """
        row = await self._session.get(BoardCallModel, call_id, populate_existing=True)
        return None if row is None else _call(row)

    async def of_session(self, session_id: uuid.UUID) -> Sequence[BoardCall]:
        """List a session's calls in order.

        Args:
            session_id: uuid.UUID - The session.

        Returns:
            Sequence[BoardCall] - Its calls.

        """
        rows = await self._session.scalars(
            select(BoardCallModel)
            .where(BoardCallModel.session_id == session_id)
            .order_by(BoardCallModel.called_at),
        )
        return [_call(row) for row in rows]

    async def counts_of_group(self, group_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Count each student's calls over a group's sessions.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            dict[uuid.UUID, int] - Calls per student who was called at least once.

        """
        rows = await self._session.execute(
            select(BoardCallModel.student_id, func.count())
            .join(SessionModel, SessionModel.id == BoardCallModel.session_id)
            .where(SessionModel.group_id == group_id)
            .group_by(BoardCallModel.student_id),
        )
        return {row[0]: row[1] for row in rows}

    async def set_entry(self, call_id: uuid.UUID, entry_id: uuid.UUID | None) -> None:
        """Tie a call to its points in the ledger.

        Args:
            call_id: uuid.UUID - The call.
            entry_id: uuid.UUID | None - The entry, or None to untie.

        """
        _ = await self._session.execute(
            update(BoardCallModel)
            .where(BoardCallModel.id == call_id)
            .values(entry_id=entry_id),
        )

    async def delete(self, call_id: uuid.UUID) -> None:
        """Delete a call.

        Args:
            call_id: uuid.UUID - It.

        """
        _ = await self._session.execute(
            delete(BoardCallModel).where(BoardCallModel.id == call_id),
        )


def _session(row: SessionModel) -> Session:
    return Session(
        session_id=row.id,
        group_id=row.group_id,
        starts_at=row.starts_at,
        topic=row.topic,
        attendance_item_id=row.attendance_item_id,
    )


def _call(row: BoardCallModel) -> BoardCall:
    return BoardCall(
        call_id=row.id,
        session_id=row.session_id,
        student_id=row.student_id,
        mode=BoardMode(row.mode),
        task=row.task,
        entry_id=row.entry_id,
        called_at=row.called_at,
    )
