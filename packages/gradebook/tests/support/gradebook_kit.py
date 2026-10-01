"""The ledger's use cases over one session, for the integration tests of every package."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.gradebook.application.services import Ledger
from smr.gradebook.application.use_cases import (
    AddPoints,
    ApplyDefaultScheme,
    CreateItem,
    CreateWorkType,
    DeleteWorkType,
    EditEntry,
    GroupSheet,
    ItemGrades,
    SetItemGrades,
    StudentReport,
    UpdateWorkType,
)
from smr.gradebook.infrastructure.repositories import (
    SqlAlchemyEntries,
    SqlAlchemyItems,
    SqlAlchemyWorkTypes,
)

if TYPE_CHECKING:
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("Gradebook", "gradebook")


@final
class Gradebook:
    """The ledger's use cases bound to one session, next to the roster's."""

    def __init__(self, session: AsyncSession, roster: Roster) -> None:
        work_types = SqlAlchemyWorkTypes(session)
        items = SqlAlchemyItems(session)
        entries = SqlAlchemyEntries(session)
        uow = SqlAlchemyUnitOfWork(session)
        audit = SqlAlchemyAuditLog(session)
        guard = AdminGuard({1})
        self.roster: Roster = roster
        self.ledger: Ledger = Ledger(
            work_types,
            items,
            entries,
            roster.api,
            audit,
            roster.clock,
        )
        self.scheme: ApplyDefaultScheme = ApplyDefaultScheme(
            work_types,
            roster.api,
            uow,
            audit,
            guard,
        )
        self.create_type: CreateWorkType = CreateWorkType(
            work_types,
            roster.api,
            uow,
            audit,
            guard,
        )
        self.update_type: UpdateWorkType = UpdateWorkType(
            work_types,
            roster.api,
            uow,
            audit,
            guard,
        )
        self.delete_type: DeleteWorkType = DeleteWorkType(
            work_types,
            roster.api,
            uow,
            audit,
            guard,
        )
        self.create_item: CreateItem = CreateItem(
            self.ledger,
            work_types,
            roster.api,
            uow,
            audit,
            guard,
            roster.clock,
        )
        self.item_grades: ItemGrades = ItemGrades(items, entries, roster.api, guard)
        self.set_grades: SetItemGrades = SetItemGrades(self.ledger, uow, guard)
        self.add_points: AddPoints = AddPoints(self.ledger, uow, guard)
        self.edit: EditEntry = EditEntry(self.ledger, uow, guard)
        self.report: StudentReport = StudentReport(self.ledger, roster.api)
        self.sheet: GroupSheet = GroupSheet(self.ledger, roster.api, guard)


@pytest.fixture
def gradebook(session: AsyncSession, roster: Roster) -> Gradebook:
    """Give the ledger's use cases over the test's session."""
    return Gradebook(session, roster)
