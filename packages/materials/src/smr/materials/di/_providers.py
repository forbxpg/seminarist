"""Materials' repositories and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.materials.application.ports import MaterialFileRepository, MaterialRepository
from smr.materials.application.use_cases import (
    AddMaterialFile,
    CreateMaterial,
    DeleteGroupMaterialFiles,
    DeleteMaterial,
    ListMaterials,
    MaterialFiles,
    PublishedMaterials,
    PublishMaterial,
    RemoveMaterialFile,
    UnpublishMaterial,
)
from smr.materials.infrastructure.repositories import (
    SqlAlchemyMaterialFiles,
    SqlAlchemyMaterials,
)


@final
class MaterialsProvider(Provider):
    """Everything of materials, built per update or task."""

    scope = Scope.REQUEST

    materials = provide(SqlAlchemyMaterials, provides=MaterialRepository)
    files = provide(SqlAlchemyMaterialFiles, provides=MaterialFileRepository)

    use_cases = provide_all(
        AddMaterialFile,
        CreateMaterial,
        DeleteGroupMaterialFiles,
        DeleteMaterial,
        ListMaterials,
        MaterialFiles,
        PublishMaterial,
        PublishedMaterials,
        RemoveMaterialFile,
        UnpublishMaterial,
    )
