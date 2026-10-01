"""Create the materials schema: seminar cards and their files.

Revision ID: ce87adb31c61
Revises: b09c63eb4201
Create Date: 2026-10-02 01:56:06.636224

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.materials.infrastructure.models import SCHEMA
from smr.migrator.ops import create_schema, drop_schema

revision = "ce87adb31c61"
down_revision = "b09c63eb4201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "material",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'published') = (published_at IS NOT NULL)",
            name=op.f("ck_material_published_at_iff_published"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published')",
            name=op.f("ck_material_status_known"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200",
            name=op.f("ck_material_title_length"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_material_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_materials_material_group_id"),
        "material",
        ["group_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "material_file",
        sa.Column("material_id", sa.UUID(), nullable=False),
        sa.Column("tg_file_id", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('jpg', 'png', 'webp', 'heic', 'pdf', 'docx')",
            name=op.f("ck_material_file_kind_known"),
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["materials.material.id"],
            name=op.f("fk_material_file_material_id_material"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_file")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_materials_material_file_material_id"),
        "material_file",
        ["material_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_index(
        op.f("ix_materials_material_file_material_id"),
        table_name="material_file",
        schema=SCHEMA,
    )
    op.drop_table("material_file", schema=SCHEMA)
    op.drop_index(
        op.f("ix_materials_material_group_id"),
        table_name="material",
        schema=SCHEMA,
    )
    op.drop_table("material", schema=SCHEMA)
    drop_schema(SCHEMA)
