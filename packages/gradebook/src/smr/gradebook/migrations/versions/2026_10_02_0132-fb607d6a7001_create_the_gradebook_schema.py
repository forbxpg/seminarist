"""Create the gradebook schema: work types, items and the ledger.

Revision ID: fb607d6a7001
Revises: 8fd5d770bd7c
Create Date: 2026-10-02 01:32:54.188236

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.gradebook.infrastructure.models import SCHEMA
from smr.migrator.ops import create_schema, drop_schema

revision = "fb607d6a7001"
down_revision = "8fd5d770bd7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "work_type",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("cap", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column(
            "in_priority",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('homework', 'test', 'attendance', 'board', 'teacher', 'other')",
            name=op.f("ck_work_type_kind_known"),
        ),
        sa.CheckConstraint(
            "mode IN ('proportional', 'accumulating')",
            name=op.f("ck_work_type_mode_known"),
        ),
        sa.CheckConstraint("cap > 0", name=op.f("ck_work_type_cap_positive")),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 100",
            name=op.f("ck_work_type_title_length"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_work_type_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_type")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_gradebook_work_type_group_id"),
        "work_type",
        ["group_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "uq_work_type_group_id_single_kind",
        "work_type",
        ["group_id", "kind"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("kind IN ('attendance', 'board')"),
    )
    _ = op.create_table(
        "grade_item",
        sa.Column("work_type_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("max_points", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("counts_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200",
            name=op.f("ck_grade_item_title_length"),
        ),
        sa.CheckConstraint(
            "max_points > 0",
            name=op.f("ck_grade_item_max_points_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["work_type_id"],
            ["gradebook.work_type.id"],
            name=op.f("fk_grade_item_work_type_id_work_type"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grade_item")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_gradebook_grade_item_work_type_id"),
        "grade_item",
        ["work_type_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "grade_entry",
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("work_type_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("points", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column(
            "excused",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("graded_by", sa.BigInteger(), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT excused OR (points = 0 AND item_id IS NOT NULL)",
            name=op.f("ck_grade_entry_excused_is_an_item_at_zero"),
        ),
        sa.CheckConstraint(
            "points >= 0",
            name=op.f("ck_grade_entry_points_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["gradebook.grade_item.id"],
            name=op.f("fk_grade_entry_item_id_grade_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_grade_entry_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_type_id"],
            ["gradebook.work_type.id"],
            name=op.f("fk_grade_entry_work_type_id_work_type"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grade_entry")),
        sa.UniqueConstraint(
            "student_id",
            "item_id",
            name="uq_grade_entry_student_id_item_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_gradebook_grade_entry_item_id"),
        "grade_entry",
        ["item_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_gradebook_grade_entry_student_id"),
        "grade_entry",
        ["student_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_gradebook_grade_entry_work_type_id"),
        "grade_entry",
        ["work_type_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_index(
        op.f("ix_gradebook_grade_entry_work_type_id"),
        table_name="grade_entry",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_gradebook_grade_entry_student_id"),
        table_name="grade_entry",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_gradebook_grade_entry_item_id"),
        table_name="grade_entry",
        schema=SCHEMA,
    )
    op.drop_table("grade_entry", schema=SCHEMA)
    op.drop_index(
        op.f("ix_gradebook_grade_item_work_type_id"),
        table_name="grade_item",
        schema=SCHEMA,
    )
    op.drop_table("grade_item", schema=SCHEMA)
    op.drop_index(
        "uq_work_type_group_id_single_kind",
        table_name="work_type",
        schema=SCHEMA,
        postgresql_where=sa.text("kind IN ('attendance', 'board')"),
    )
    op.drop_index(
        op.f("ix_gradebook_work_type_group_id"),
        table_name="work_type",
        schema=SCHEMA,
    )
    op.drop_table("work_type", schema=SCHEMA)
    drop_schema(SCHEMA)
