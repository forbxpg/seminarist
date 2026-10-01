"""What the teacher and the students do with seminar materials."""

from __future__ import annotations

from ._student import MaterialFiles, PublishedMaterials
from ._teacher import (
    AddMaterialFile,
    CreateMaterial,
    DeleteGroupMaterialFiles,
    DeleteMaterial,
    ListMaterials,
    MaterialUpload,
    PublishMaterial,
    RemoveMaterialFile,
    UnpublishMaterial,
)

__all__ = (
    "AddMaterialFile",
    "CreateMaterial",
    "DeleteGroupMaterialFiles",
    "DeleteMaterial",
    "ListMaterials",
    "MaterialFiles",
    "MaterialUpload",
    "PublishMaterial",
    "PublishedMaterials",
    "RemoveMaterialFile",
    "UnpublishMaterial",
)
