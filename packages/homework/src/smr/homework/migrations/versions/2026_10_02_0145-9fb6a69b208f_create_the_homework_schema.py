"""Create the homework schema: assignments, submissions and their files.

Revision ID: 9fb6a69b208f
Revises: a36a192fd3e6
Create Date: 2026-10-02 01:45:05.525990

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.homework.infrastructure.models import SCHEMA
from smr.migrator.ops import create_schema, drop_schema

revision = "9fb6a69b208f"
down_revision = "a36a192fd3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "assignment",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("work_type_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("statement_file_id", sa.Text(), nullable=True),
        sa.Column("statement_path", sa.Text(), nullable=True),
        sa.Column("statement_kind", sa.Text(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_points", sa.Numeric(precision=6, scale=2), nullable=False),
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
            "statement_kind IS NULL OR statement_kind IN ('jpg', 'png', 'webp', 'heic', 'pdf', 'docx')",
            name=op.f("ck_assignment_statement_kind_known"),
        ),
        sa.CheckConstraint(
            "(statement_file_id IS NULL) = (statement_path IS NULL)",
            name=op.f("ck_assignment_statement_path_with_id"),
        ),
        sa.CheckConstraint(
            "(statement_path IS NULL) = (statement_kind IS NULL)",
            name=op.f("ck_assignment_statement_kind_with_path"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200",
            name=op.f("ck_assignment_title_length"),
        ),
        sa.CheckConstraint(
            "max_points > 0",
            name=op.f("ck_assignment_max_points_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_assignment_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["gradebook.grade_item.id"],
            name=op.f("fk_assignment_item_id_grade_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["work_type_id"],
            ["gradebook.work_type.id"],
            name=op.f("fk_assignment_work_type_id_work_type"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_homework_assignment_deadline"),
        "assignment",
        ["deadline"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_homework_assignment_group_id"),
        "assignment",
        ["group_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "submission",
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_late",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("entry_id", sa.UUID(), nullable=True),
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
            "(status = 'draft') = (sent_at IS NULL)",
            name=op.f("ck_submission_sent_unless_draft"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'superseded', 'graded')",
            name=op.f("ck_submission_status_known"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_submission_version_positive")),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["homework.assignment.id"],
            name=op.f("fk_submission_assignment_id_assignment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["gradebook.grade_entry.id"],
            name=op.f("fk_submission_entry_id_grade_entry"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_submission_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission")),
        sa.UniqueConstraint(
            "assignment_id",
            "student_id",
            "version",
            name="version_once",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_homework_submission_assignment_id"),
        "submission",
        ["assignment_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_homework_submission_student_id"),
        "submission",
        ["student_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "uq_submission_one_draft",
        "submission",
        ["assignment_id", "student_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_submission_one_live",
        "submission",
        ["assignment_id", "student_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status IN ('submitted', 'graded')"),
    )
    _ = op.create_table(
        "submission_file",
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("tg_file_id", sa.Text(), nullable=False),
        sa.Column("tg_file_unique_id", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('jpg', 'png', 'webp', 'heic', 'pdf', 'docx')",
            name=op.f("ck_submission_file_kind_known"),
        ),
        sa.CheckConstraint("size > 0", name=op.f("ck_submission_file_size_positive")),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["homework.submission.id"],
            name=op.f("fk_submission_file_submission_id_submission"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission_file")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_homework_submission_file_submission_id"),
        "submission_file",
        ["submission_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_index(
        op.f("ix_homework_submission_file_submission_id"),
        table_name="submission_file",
        schema=SCHEMA,
    )
    op.drop_table("submission_file", schema=SCHEMA)
    op.drop_index(
        "uq_submission_one_live",
        table_name="submission",
        schema=SCHEMA,
        postgresql_where=sa.text("status IN ('submitted', 'graded')"),
    )
    op.drop_index(
        "uq_submission_one_draft",
        table_name="submission",
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.drop_index(
        op.f("ix_homework_submission_student_id"),
        table_name="submission",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_homework_submission_assignment_id"),
        table_name="submission",
        schema=SCHEMA,
    )
    op.drop_table("submission", schema=SCHEMA)
    op.drop_index(
        op.f("ix_homework_assignment_group_id"),
        table_name="assignment",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_homework_assignment_deadline"),
        table_name="assignment",
        schema=SCHEMA,
    )
    op.drop_table("assignment", schema=SCHEMA)
    drop_schema(SCHEMA)
