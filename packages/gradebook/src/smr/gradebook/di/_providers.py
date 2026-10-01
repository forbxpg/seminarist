"""The ledger's repositories, service, contract and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.gradebook.application.contracts import GradebookApi
from smr.gradebook.application.ports import (
    EntryRepository,
    ItemRepository,
    WorkTypeRepository,
)
from smr.gradebook.application.services import Ledger
from smr.gradebook.application.use_cases import (
    AddPoints,
    ApplyDefaultScheme,
    CreateItem,
    CreateWorkType,
    DeleteEntry,
    DeleteItem,
    DeleteWorkType,
    EditEntry,
    GroupSheet,
    ItemGrades,
    ListItems,
    ListWorkTypes,
    SetItemGrades,
    StudentEntries,
    StudentReport,
    UpdateWorkType,
)
from smr.gradebook.infrastructure.repositories import (
    SqlAlchemyEntries,
    SqlAlchemyItems,
    SqlAlchemyWorkTypes,
)


@final
class GradebookProvider(Provider):
    """Everything of the ledger, built per update or task."""

    scope = Scope.REQUEST

    work_types = provide(SqlAlchemyWorkTypes, provides=WorkTypeRepository)
    items = provide(SqlAlchemyItems, provides=ItemRepository)
    entries = provide(SqlAlchemyEntries, provides=EntryRepository)
    ledger = provide(Ledger)

    @provide
    def api(self, ledger: Ledger) -> GradebookApi:
        """Let the neighbours write points through the ledger.

        Args:
            ledger: Ledger - The ledger.

        Returns:
            GradebookApi - The contract.

        """
        return ledger

    use_cases = provide_all(
        AddPoints,
        ApplyDefaultScheme,
        CreateItem,
        CreateWorkType,
        DeleteEntry,
        DeleteItem,
        DeleteWorkType,
        EditEntry,
        GroupSheet,
        ItemGrades,
        ListItems,
        ListWorkTypes,
        SetItemGrades,
        StudentEntries,
        StudentReport,
        UpdateWorkType,
    )
