"""The roster's read-only contract over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy.ext.asyncio import AsyncSession

from smr.roster.domain import CONSENT_VERSION, BindingStatus, Group, Student

from ._groups import SqlAlchemyGroups
from ._students import SqlAlchemyStudents


@final
class SqlAlchemyRosterApi:
    """`RosterApi` in the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._groups: SqlAlchemyGroups = SqlAlchemyGroups(session)
        self._students: SqlAlchemyStudents = SqlAlchemyStudents(session)

    async def group(self, group_id: uuid.UUID) -> Group | None:
        """Read a group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Group | None - It, or None.

        """
        return await self._groups.get(group_id)

    async def student(self, student_id: uuid.UUID) -> Student | None:
        """Read a roster row.

        Args:
            student_id: uuid.UUID - The row.

        Returns:
            Student | None - It, or None.

        """
        return await self._students.get(student_id)

    async def students_of(self, group_id: uuid.UUID) -> Sequence[Student]:
        """List a group's roster by name.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Student] - The roster.

        """
        return await self._students.of_group(group_id)

    async def consented(self, student_id: uuid.UUID) -> bool:
        """Tell whether a row accepted the current privacy notice.

        Args:
            student_id: uuid.UUID - The row.

        Returns:
            bool - True when its consent version is the current one.

        """
        student = await self._students.get(student_id)
        return student is not None and student.consent_version == CONSENT_VERSION

    async def bound_student(
        self,
        tg_user_id: int,
        group_id: uuid.UUID,
    ) -> Student | None:
        """Find the row an account holds, approved, in a group.

        Args:
            tg_user_id: int - Telegram user id.
            group_id: uuid.UUID - The group.

        Returns:
            Student | None - The bound row, or None.

        """
        for student in await self._students.of_account(tg_user_id):
            if student.group_id == group_id and student.binding is BindingStatus.BOUND:
                return student
        return None
