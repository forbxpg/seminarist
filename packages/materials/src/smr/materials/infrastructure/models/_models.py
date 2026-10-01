"""Rows of cards and their files."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- SQLAlchemy reads it at runtime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from smr.core.database import UUIDPkMixin, make_metadata
from smr.roster.infrastructure.models import GroupModel

SCHEMA = "materials"
METADATA = make_metadata(SCHEMA)


class MaterialsBase(DeclarativeBase):
    """Base of materials' ORM models."""

    metadata: ClassVar[MetaData] = METADATA


class MaterialModel(UUIDPkMixin, MaterialsBase):
    """A seminar card."""

    __tablename__: str = "material"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("status IN ('draft', 'published')", name="status_known"),
        CheckConstraint(
            "(status = 'published') = (published_at IS NOT NULL)",
            name="published_at_iff_published",
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(GroupModel.id, ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class MaterialFileModel(UUIDPkMixin, MaterialsBase):
    """A file of a card."""

    __tablename__: str = "material_file"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            "kind IN ('jpg', 'png', 'webp', 'heic', 'pdf', 'docx')",
            name="kind_known",
        ),
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.material.id", ondelete="CASCADE"),
        index=True,
    )
    tg_file_id: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer)
