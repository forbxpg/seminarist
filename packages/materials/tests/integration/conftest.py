"""Integration fixtures: the database, the roster, notifications and materials."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from notifications_kit import notifications
from roster_kit import roster
from smr_database import database_url, session

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.database import SqlAlchemyUnitOfWork
from smr.core.files import FileStore
from smr.materials.application.use_cases import (
    AddMaterialFile,
    CreateMaterial,
    DeleteMaterial,
    ListMaterials,
    MaterialFiles,
    PublishedMaterials,
    PublishMaterial,
    UnpublishMaterial,
)
from smr.materials.infrastructure.repositories import (
    SqlAlchemyMaterialFiles,
    SqlAlchemyMaterials,
)

if TYPE_CHECKING:
    from pathlib import Path

    from notifications_kit import Notifications
    from roster_kit import Roster
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = (
    "Materials",
    "database_url",
    "materials",
    "notifications",
    "roster",
    "session",
)


@final
class Materials:
    """Materials' use cases over one session and a temporary disk."""

    def __init__(
        self,
        session: AsyncSession,
        roster: Roster,
        notifications: Notifications,
        data_dir: Path,
    ) -> None:
        materials = SqlAlchemyMaterials(session)
        stored = SqlAlchemyMaterialFiles(session)
        uow = SqlAlchemyUnitOfWork(session)
        audit = SqlAlchemyAuditLog(session)
        guard = AdminGuard({1})
        files = FileStore(data_dir, max_bytes=1024)
        clock = roster.clock
        self.roster: Roster = roster
        self.notifications: Notifications = notifications
        self.files: FileStore = files
        self.create: CreateMaterial = CreateMaterial(
            materials,
            roster.api,
            uow,
            audit,
            guard,
            clock,
        )
        self.add_file: AddMaterialFile = AddMaterialFile(
            materials,
            stored,
            files,
            uow,
            guard,
            clock,
        )
        self.publish: PublishMaterial = PublishMaterial(
            materials,
            stored,
            roster.api,
            notifications.notifier,
            uow,
            audit,
            guard,
            clock,
        )
        self.unpublish: UnpublishMaterial = UnpublishMaterial(
            materials,
            uow,
            audit,
            guard,
        )
        self.delete: DeleteMaterial = DeleteMaterial(
            materials,
            stored,
            files,
            uow,
            audit,
            guard,
        )
        self.list: ListMaterials = ListMaterials(materials, stored, guard)
        self.published: PublishedMaterials = PublishedMaterials(materials, roster.api)
        self.files_of: MaterialFiles = MaterialFiles(materials, stored, roster.api)


@pytest.fixture
def materials(
    session: AsyncSession,
    roster: Roster,
    notifications: Notifications,
    tmp_path: Path,
) -> Materials:
    """Give materials' use cases over the test's session and a temporary disk."""
    return Materials(session, roster, notifications, tmp_path)
