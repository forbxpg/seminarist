"""The graded items over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smr.gradebook.domain import GradeItem
from smr.gradebook.infrastructure.models import ItemModel, WorkTypeModel

_Row = ItemModel


@final
class SqlAlchemyItems:
    """`ItemRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, item: GradeItem) -> None:
        """Add an item.

        Args:
            item: GradeItem - It.

        """
        self._session.add(
            _Row(
                id=item.item_id,
                work_type_id=item.work_type_id,
                title=item.title,
                max_points=item.max_points,
                counts_from=item.counts_from,
            ),
        )
        await self._session.flush()

    async def get(self, item_id: uuid.UUID) -> GradeItem | None:
        """Read an item.

        Args:
            item_id: uuid.UUID - It.

        Returns:
            GradeItem | None - It, or None.

        """
        row = await self._session.get(_Row, item_id, populate_existing=True)
        return None if row is None else _domain(row)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[GradeItem]:
        """List a group's items, oldest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[GradeItem] - Its items.

        """
        rows = await self._session.scalars(
            select(_Row)
            .join(WorkTypeModel, WorkTypeModel.id == _Row.work_type_id)
            .where(WorkTypeModel.group_id == group_id)
            .order_by(_Row.counts_from),
        )
        return [_domain(row) for row in rows]

    async def of_work_type(self, work_type_id: uuid.UUID) -> Sequence[GradeItem]:
        """List a work type's items, oldest first.

        Args:
            work_type_id: uuid.UUID - The work type.

        Returns:
            Sequence[GradeItem] - Its items.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.work_type_id == work_type_id)
            .order_by(_Row.counts_from),
        )
        return [_domain(row) for row in rows]

    async def update(self, item: GradeItem) -> None:
        """Store a changed item.

        Args:
            item: GradeItem - It, changed.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == item.item_id)
            .values(
                work_type_id=item.work_type_id,
                title=item.title,
                max_points=item.max_points,
                counts_from=item.counts_from,
            ),
        )

    async def delete(self, item_id: uuid.UUID) -> None:
        """Delete an item with its entries.

        Args:
            item_id: uuid.UUID - It.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == item_id))


def _domain(row: ItemModel) -> GradeItem:
    return GradeItem(
        item_id=row.id,
        work_type_id=row.work_type_id,
        title=row.title,
        max_points=row.max_points,
        counts_from=row.counts_from,
    )
