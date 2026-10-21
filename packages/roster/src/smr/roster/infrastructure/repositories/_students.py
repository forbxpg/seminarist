"""The roster rows over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import final

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from smr.roster.domain import BindingStatus, Student
from smr.roster.infrastructure.models import STUDENT_NAME_UNIQUE, StudentModel

_Row = StudentModel


@final
class SqlAlchemyStudents:
    """`StudentRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add_many(self, group_id: uuid.UUID, names: Sequence[str]) -> int:
        """Add names to a group's roster; names it already has are skipped.

        Args:
            group_id: uuid.UUID - The group.
            names: Sequence[str] - Tidy distinct names.

        Returns:
            int - How many were added.

        """
        if not names:
            return 0
        added = await self._session.scalars(
            insert(_Row)
            .values([{"group_id": group_id, "full_name": name} for name in names])
            .on_conflict_do_nothing(constraint=STUDENT_NAME_UNIQUE)
            .returning(_Row.id),
        )
        return len(added.all())

    async def get(self, student_id: uuid.UUID) -> Student | None:
        """Read a roster row.

        Args:
            student_id: uuid.UUID - The row.

        Returns:
            Student | None - It, or None.

        """
        row = await self._session.get(_Row, student_id, populate_existing=True)
        return None if row is None else to_student(row)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Student]:
        """List a group's roster by name.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Student] - The roster.

        """
        rows = await self._session.scalars(
            select(_Row).where(_Row.group_id == group_id).order_by(_Row.full_name),
        )
        return [to_student(row) for row in rows]

    async def of_account(self, tg_user_id: int) -> Sequence[Student]:
        """List every row a Telegram account claims or holds.

        Args:
            tg_user_id: int - Telegram user id.

        Returns:
            Sequence[Student] - The rows.

        """
        rows = await self._session.scalars(
            select(_Row).where(_Row.tg_user_id == tg_user_id).order_by(_Row.created_at),
        )
        return [to_student(row) for row in rows]

    async def pending(self) -> Sequence[Student]:
        """List the rows waiting for the teacher, oldest claim first.

        Returns:
            Sequence[Student] - The rows.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.binding == BindingStatus.PENDING.value)
            .order_by(_Row.binding_requested_at),
        )
        return [to_student(row) for row in rows]

    async def claim(
        self,
        student_id: uuid.UUID,
        tg_user_id: int,
        consent_version: str,
        now: datetime,
    ) -> bool:
        """Claim a row for an account, only if nobody holds it.

        Args:
            student_id: uuid.UUID - The row.
            tg_user_id: int - The claiming account.
            consent_version: str - The privacy notice it accepted.
            now: datetime - When.

        Returns:
            bool - False when someone already claims or holds the row.

        """
        claimed = await self._session.scalar(
            update(_Row)
            .where(_Row.id == student_id, _Row.tg_user_id.is_(None))
            .values(
                tg_user_id=tg_user_id,
                binding=BindingStatus.PENDING.value,
                binding_requested_at=now,
                consent_version=consent_version,
                consent_at=now,
            )
            .returning(_Row.id),
        )
        return claimed is not None

    async def set_binding(self, student_id: uuid.UUID, binding: BindingStatus) -> None:
        """Move a claimed row to another binding state, keeping its account.

        Args:
            student_id: uuid.UUID - The row.
            binding: BindingStatus - Pending or bound.

        """
        _ = await self._session.execute(
            update(_Row).where(_Row.id == student_id).values(binding=binding.value),
        )

    async def set_consent(self, tg_user_id: int, version: str, at: datetime) -> int:
        """Record the current notice on every bound row of an account.

        Args:
            tg_user_id: int - The account.
            version: str - The notice it accepted.
            at: datetime - When.

        Returns:
            int - How many rows were updated.

        """
        updated = await self._session.scalars(
            update(_Row)
            .where(
                _Row.tg_user_id == tg_user_id,
                _Row.binding == BindingStatus.BOUND.value,
            )
            .values(consent_version=version, consent_at=at)
            .returning(_Row.id),
        )
        return len(updated.all())

    async def release(self, student_id: uuid.UUID) -> None:
        """Unbind a row: forget its account and consent.

        Args:
            student_id: uuid.UUID - The row.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == student_id)
            .values(
                tg_user_id=None,
                binding=BindingStatus.UNBOUND.value,
                binding_requested_at=None,
                consent_version=None,
                consent_at=None,
            ),
        )

    async def rename(self, student_id: uuid.UUID, full_name: str) -> None:
        """Rename a row.

        Args:
            student_id: uuid.UUID - The row.
            full_name: str - Its new tidy name.

        """
        _ = await self._session.execute(
            update(_Row).where(_Row.id == student_id).values(full_name=full_name),
        )

    async def set_journal_no(self, student_id: uuid.UUID, number: int | None) -> None:
        """Set or clear a row's journal number.

        Args:
            student_id: uuid.UUID - The row.
            number: int | None - The number, or None to clear it.

        """
        _ = await self._session.execute(
            update(_Row).where(_Row.id == student_id).values(journal_no=number),
        )

    async def delete(self, student_id: uuid.UUID) -> None:
        """Delete a row.

        Args:
            student_id: uuid.UUID - The row.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == student_id))


def to_student(row: StudentModel) -> Student:
    """Map a row to the domain student.

    Args:
        row: StudentModel - The row.

    Returns:
        Student - The student.

    """
    return Student(
        student_id=row.id,
        group_id=row.group_id,
        full_name=row.full_name,
        tg_user_id=row.tg_user_id,
        binding=BindingStatus(row.binding),
        binding_requested_at=row.binding_requested_at,
        consent_version=row.consent_version,
        consent_at=row.consent_at,
        journal_no=row.journal_no,
    )
