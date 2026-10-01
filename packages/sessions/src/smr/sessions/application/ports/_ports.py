"""Ports of sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence

    from smr.sessions.domain import AttendanceStatus, BoardCall, Session


class SessionRepository(Protocol):
    """Every session."""

    async def add(self, session: Session) -> None:
        """Add a session.

        Args:
            session: Session - It.

        """
        ...

    async def get(self, session_id: uuid.UUID) -> Session | None:
        """Read a session.

        Args:
            session_id: uuid.UUID - It.

        Returns:
            Session | None - It, or None.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Session]:
        """List a group's sessions, the latest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Session] - Its sessions.

        """
        ...

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
        ...

    async def delete(self, session_id: uuid.UUID) -> None:
        """Delete a session with its attendance and calls.

        Args:
            session_id: uuid.UUID - It.

        """
        ...


class AttendanceRepository(Protocol):
    """Every session's attendance."""

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
        ...

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
        ...


class BoardCallRepository(Protocol):
    """Every board call."""

    async def add(self, call: BoardCall) -> None:
        """Add a call.

        Args:
            call: BoardCall - It.

        """
        ...

    async def get(self, call_id: uuid.UUID) -> BoardCall | None:
        """Read a call.

        Args:
            call_id: uuid.UUID - It.

        Returns:
            BoardCall | None - It, or None.

        """
        ...

    async def of_session(self, session_id: uuid.UUID) -> Sequence[BoardCall]:
        """List a session's calls in order.

        Args:
            session_id: uuid.UUID - The session.

        Returns:
            Sequence[BoardCall] - Its calls.

        """
        ...

    async def counts_of_group(self, group_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Count each student's calls over a group's sessions.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            dict[uuid.UUID, int] - Calls per student who was called at least once.

        """
        ...

    async def set_entry(self, call_id: uuid.UUID, entry_id: uuid.UUID | None) -> None:
        """Tie a call to its points in the ledger.

        Args:
            call_id: uuid.UUID - The call.
            entry_id: uuid.UUID | None - The entry, or None to untie.

        """
        ...

    async def delete(self, call_id: uuid.UUID) -> None:
        """Delete a call.

        Args:
            call_id: uuid.UUID - It.

        """
        ...
