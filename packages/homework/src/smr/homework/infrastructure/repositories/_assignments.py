"""The assignments over the session."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import delete, select, update

from smr.core.files import FileKind
from smr.homework.domain import Assignment, StatementFile
from smr.homework.infrastructure.models import AssignmentModel

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_Row = AssignmentModel


@final
class SqlAlchemyAssignments:
    """`AssignmentRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, assignment: Assignment) -> None:
        """Add an assignment.

        Args:
            assignment: Assignment - It.

        """
        statement = assignment.statement
        self._session.add(
            _Row(
                id=assignment.assignment_id,
                group_id=assignment.group_id,
                work_type_id=assignment.work_type_id,
                item_id=assignment.item_id,
                title=assignment.title,
                body=assignment.body,
                statement_file_id=None if statement is None else statement.tg_file_id,
                statement_path=None if statement is None else statement.path,
                statement_kind=None if statement is None else statement.kind.value,
                deadline=assignment.deadline,
                max_points=assignment.max_points,
            ),
        )
        await self._session.flush()

    async def get(self, assignment_id: uuid.UUID) -> Assignment | None:
        """Read an assignment.

        Args:
            assignment_id: uuid.UUID - It.

        Returns:
            Assignment | None - It, or None.

        """
        row = await self._session.get(_Row, assignment_id, populate_existing=True)
        return None if row is None else _domain(row)

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Assignment]:
        """List a group's assignments, the latest deadline first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Assignment] - Its assignments.

        """
        rows = await self._session.scalars(
            select(_Row)
            .where(_Row.group_id == group_id)
            .order_by(_Row.deadline.desc()),
        )
        return [_domain(row) for row in rows]

    async def due_between(self, start: datetime, end: datetime) -> Sequence[Assignment]:
        """List the assignments with a deadline in a window.

        Args:
            start: datetime - From, exclusive.
            end: datetime - To, inclusive.

        Returns:
            Sequence[Assignment] - Those assignments.

        """
        rows = await self._session.scalars(
            select(_Row).where(_Row.deadline > start, _Row.deadline <= end),
        )
        return [_domain(row) for row in rows]

    async def update(self, assignment: Assignment) -> None:
        """Store a changed assignment.

        Args:
            assignment: Assignment - It, changed.

        """
        _ = await self._session.execute(
            update(_Row)
            .where(_Row.id == assignment.assignment_id)
            .values(
                title=assignment.title,
                body=assignment.body,
                deadline=assignment.deadline,
                max_points=assignment.max_points,
            ),
        )

    async def delete(self, assignment_id: uuid.UUID) -> None:
        """Delete an assignment with its submissions.

        Args:
            assignment_id: uuid.UUID - It.

        """
        _ = await self._session.execute(delete(_Row).where(_Row.id == assignment_id))


def _domain(row: AssignmentModel) -> Assignment:
    statement = None
    if row.statement_file_id and row.statement_path and row.statement_kind:
        statement = StatementFile(
            row.statement_file_id,
            row.statement_path,
            FileKind(row.statement_kind),
        )
    return Assignment(
        assignment_id=row.id,
        group_id=row.group_id,
        work_type_id=row.work_type_id,
        item_id=row.item_id,
        title=row.title,
        body=row.body,
        statement=statement,
        deadline=row.deadline,
        max_points=row.max_points,
    )
