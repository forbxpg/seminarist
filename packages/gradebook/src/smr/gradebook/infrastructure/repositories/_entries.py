"""The entries of the ledger over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smr.gradebook.domain import GradeEntry
from smr.gradebook.infrastructure.models import EntryModel, WorkTypeModel

_Row = EntryModel


@final
class SqlAlchemyEntries:
    """`EntryRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, entry: GradeEntry) -> None:
        """Add an entry.

        Args:
            entry: GradeEntry - It.

        """
        self._session.add(
            _Row(
                id=entry.entry_id,
                student_id=entry.student_id,
                work_type_id=entry.work_type_id,
                item_id=entry.item_id,
                points=entry.points,
                excused=entry.excused,
                comment=entry.comment,
                graded_by=entry.graded_by,
                graded_at=entry.graded_at,
            ),
        )
        await self._session.flush()

    async def get(self, entry_id: uuid.UUID) -> GradeEntry | None:
        """Read an entry.

        Args:
            entry_id: uuid.UUID - It.

        Returns:
            GradeEntry | None - It, or None.

        """
        row = await self._session.get(_Row, entry_id, populate_existing=True)
        return None if row is None else _domain(row)

    async def for_item(
        self,
        student_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> GradeEntry | None:
        """Find a student's entry for an item.

        Args:
            student_id: uuid.UUID - The student.
            item_id: uuid.UUID - The item.

        Returns:
            GradeEntry | None - It, or None.

        """
        row = await self._session.scalar(
            select(_Row).where(_Row.student_id == student_id, _Row.item_id == item_id),
        )
        return None if row is None else _domain(row)

    async def of_item(self, item_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List an item's entries.

        Args:
            item_id: uuid.UUID - The item.

        Returns:
            Sequence[GradeEntry] - Its entries.

        """
        rows = await self._session.scalars(select(_Row).where(_Row.item_id == item_id))
        return [_domain(row) for row in rows]

    async def of_group(self, group_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List every entry of a group's work types.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[GradeEntry] - The entries.

        """
        rows = await self._session.scalars(
            select(_Row)
            .join(WorkTypeModel, WorkTypeModel.id == _Row.work_type_id)
            .where(WorkTypeModel.group_id == group_id),
        )
        return [_domain(row) for row in rows]

    async def of_student(self, student_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List a student's entries, newest first.

        Args:
            student_id: uuid.UUID - The student.

        Returns:
            Sequence[GradeEntry] - The entries.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.student_id == student_id)
            .order_by(_Row.graded_at.desc()),
        )
        return [_domain(row) for row in rows]

    async def retarget(self, item_id: uuid.UUID, work_type_id: uuid.UUID) -> None:
        """Point an item's entries at another work type, leaving the points.

        Args:
            item_id: uuid.UUID - The item.
            work_type_id: uuid.UUID - The work type.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.item_id == item_id)
            .values(work_type_id=work_type_id),
        )

    async def update(self, entry: GradeEntry) -> None:
        """Store a changed entry.

        Args:
            entry: GradeEntry - It, changed.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == entry.entry_id)
            .values(
                points=entry.points,
                excused=entry.excused,
                comment=entry.comment,
                graded_by=entry.graded_by,
                graded_at=entry.graded_at,
            ),
        )

    async def delete(self, entry_id: uuid.UUID) -> None:
        """Delete an entry.

        Args:
            entry_id: uuid.UUID - It.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == entry_id))


def _domain(row: EntryModel) -> GradeEntry:
    return GradeEntry(
        entry_id=row.id,
        student_id=row.student_id,
        work_type_id=row.work_type_id,
        item_id=row.item_id,
        points=row.points,
        excused=row.excused,
        comment=row.comment,
        graded_by=row.graded_by,
        graded_at=row.graded_at,
    )
