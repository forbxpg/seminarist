"""The work types over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smr.gradebook.domain import ScoringMode, WorkType, WorkTypeKind
from smr.gradebook.infrastructure.models import EntryModel, WorkTypeModel

_Row = WorkTypeModel


@final
class SqlAlchemyWorkTypes:
    """`WorkTypeRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, work_type: WorkType) -> None:
        """Add a work type.

        Args:
            work_type: WorkType - It.

        """
        self._session.add(
            _Row(
                id=work_type.work_type_id,
                group_id=work_type.group_id,
                title=work_type.title,
                kind=work_type.kind.value,
                mode=work_type.mode.value,
                cap=work_type.cap,
                in_priority=work_type.in_priority,
                position=work_type.position,
            ),
        )
        await self._session.flush()

    async def get(self, work_type_id: uuid.UUID) -> WorkType | None:
        """Read a work type.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            WorkType | None - It, or None.

        """
        row = await self._session.get(_Row, work_type_id, populate_existing=True)
        return None if row is None else _domain(row)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[WorkType]:
        """List a group's work types in report order.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[WorkType] - Its work types.

        """
        rows = await self._session.scalars(
            select(_Row).where(_Row.group_id == group_id).order_by(_Row.position),
        )
        return [_domain(row) for row in rows]

    async def of_kind(
        self,
        group_id: uuid.UUID,
        kind: WorkTypeKind,
    ) -> Sequence[WorkType]:
        """List a group's work types of a kind.

        Args:
            group_id: uuid.UUID - The group.
            kind: WorkTypeKind - The kind.

        Returns:
            Sequence[WorkType] - Those work types.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.group_id == group_id, _Row.kind == kind.value)
            .order_by(_Row.position),
        )
        return [_domain(row) for row in rows]

    async def update(self, work_type: WorkType) -> None:
        """Store a changed work type.

        Args:
            work_type: WorkType - It, changed.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == work_type.work_type_id)
            .values(
                title=work_type.title,
                cap=work_type.cap,
                in_priority=work_type.in_priority,
                position=work_type.position,
            ),
        )

    async def delete(self, work_type_id: uuid.UUID) -> None:
        """Delete a work type.

        Args:
            work_type_id: uuid.UUID - It.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == work_type_id))

    async def has_entries(self, work_type_id: uuid.UUID) -> bool:
        """Tell whether a work type has any points.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            bool - True when an entry refers to it.

        """
        found = await self._session.scalar(
            select(exists().where(EntryModel.work_type_id == work_type_id)),
        )
        return bool(found)


def _domain(row: WorkTypeModel) -> WorkType:
    return WorkType(
        work_type_id=row.id,
        group_id=row.group_id,
        title=row.title,
        kind=WorkTypeKind(row.kind),
        mode=ScoringMode(row.mode),
        cap=row.cap,
        in_priority=row.in_priority,
        position=row.position,
    )
