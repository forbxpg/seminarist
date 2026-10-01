"""Cards and their files over the SQLAlchemy session."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import delete, select, update

from smr.core.files import FileKind
from smr.materials.domain import Material, MaterialFile, MaterialStatus
from smr.materials.infrastructure.models import MaterialFileModel, MaterialModel

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


@final
class SqlAlchemyMaterials:
    """`MaterialRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, material: Material) -> None:
        """Add a card.

        Args:
            material: Material - It.

        """
        self._session.add(
            MaterialModel(
                id=material.material_id,
                group_id=material.group_id,
                title=material.title,
                status=material.status.value,
                published_at=material.published_at,
                created_at=material.created_at,
            ),
        )
        await self._session.flush()

    async def get(self, material_id: uuid.UUID) -> Material | None:
        """Read a card.

        Args:
            material_id: uuid.UUID - It.

        Returns:
            Material | None - It, or None.

        """
        row = await self._session.get(
            MaterialModel,
            material_id,
            populate_existing=True,
        )
        return None if row is None else _material(row)

    async def of_group(
        self,
        group_id: uuid.UUID,
        *,
        published_only: bool,
    ) -> Sequence[Material]:
        """List a group's cards, the newest first.

        Args:
            group_id: uuid.UUID - The group.
            published_only: bool - Only those students see.

        Returns:
            Sequence[Material] - The cards.

        """
        query = select(MaterialModel).where(MaterialModel.group_id == group_id)
        if published_only:
            query = query.where(MaterialModel.status == MaterialStatus.PUBLISHED.value)
        rows = await self._session.scalars(
            query.order_by(MaterialModel.created_at.desc()),
        )
        return [_material(row) for row in rows]

    async def set_status(
        self,
        material_id: uuid.UUID,
        status: MaterialStatus,
        published_at: datetime | None,
    ) -> None:
        """Publish or unpublish a card.

        Args:
            material_id: uuid.UUID - It.
            status: MaterialStatus - Its new status.
            published_at: datetime | None - When it was published; none for a draft.

        """
        _ = await self._session.execute(
            update(MaterialModel)
            .where(MaterialModel.id == material_id)
            .values(status=status.value, published_at=published_at),
        )

    async def delete(self, material_id: uuid.UUID) -> None:
        """Delete a card with its files' rows.

        Args:
            material_id: uuid.UUID - It.

        """
        _ = await self._session.execute(
            delete(MaterialModel).where(MaterialModel.id == material_id),
        )


@final
class SqlAlchemyMaterialFiles:
    """`MaterialFileRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, file: MaterialFile) -> None:
        """Add a file.

        Args:
            file: MaterialFile - It.

        """
        self._session.add(
            MaterialFileModel(
                id=file.file_id,
                material_id=file.material_id,
                tg_file_id=file.tg_file_id,
                path=file.path,
                kind=file.kind.value,
                size=file.size,
                position=file.position,
            ),
        )
        await self._session.flush()

    async def get(self, file_id: uuid.UUID) -> MaterialFile | None:
        """Read a file.

        Args:
            file_id: uuid.UUID - It.

        Returns:
            MaterialFile | None - It, or None.

        """
        row = await self._session.get(MaterialFileModel, file_id)
        return None if row is None else _file(row)

    async def of_material(self, material_id: uuid.UUID) -> Sequence[MaterialFile]:
        """List a card's files in order.

        Args:
            material_id: uuid.UUID - The card.

        Returns:
            Sequence[MaterialFile] - Its files.

        """
        rows = await self._session.scalars(
            select(MaterialFileModel)
            .where(MaterialFileModel.material_id == material_id)
            .order_by(MaterialFileModel.position),
        )
        return [_file(row) for row in rows]

    async def delete(self, file_id: uuid.UUID) -> None:
        """Delete a file's row.

        Args:
            file_id: uuid.UUID - It.

        """
        _ = await self._session.execute(
            delete(MaterialFileModel).where(MaterialFileModel.id == file_id),
        )

    async def paths_of_group(self, group_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of a group's files.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[str] - The paths.

        """
        rows = await self._session.scalars(
            select(MaterialFileModel.path)
            .join(MaterialModel, MaterialModel.id == MaterialFileModel.material_id)
            .where(MaterialModel.group_id == group_id),
        )
        return list(rows)


def _material(row: MaterialModel) -> Material:
    return Material(
        material_id=row.id,
        group_id=row.group_id,
        title=row.title,
        status=MaterialStatus(row.status),
        published_at=row.published_at,
        created_at=row.created_at,
    )


def _file(row: MaterialFileModel) -> MaterialFile:
    return MaterialFile(
        file_id=row.id,
        material_id=row.material_id,
        tg_file_id=row.tg_file_id,
        path=row.path,
        kind=FileKind(row.kind),
        size=row.size,
        position=row.position,
    )
