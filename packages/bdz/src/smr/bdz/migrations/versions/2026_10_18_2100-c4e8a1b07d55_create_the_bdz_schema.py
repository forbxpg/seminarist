"""Create the bdz schema: assignments, tasks and submissions.

Revision ID: c4e8a1b07d55
Revises: f3a91c0e7b44
Create Date: 2026-10-18 21:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.bdz.infrastructure.models import SCHEMA
from smr.migrator.ops import create_schema, drop_schema

revision = "c4e8a1b07d55"
down_revision = "f3a91c0e7b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "assignment",
        sa.Column("bdz_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("work_type_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_points", sa.Numeric(6, 2), nullable=False),
        sa.Column("statement_path", sa.Text(), nullable=False),
        sa.Column("statement_tg_file_id", sa.Text(), nullable=False),
        sa.Column("statement_pages", sa.Integer(), nullable=False),
        sa.Column("solutions_path", sa.Text(), nullable=False),
        sa.Column("solutions_tg_file_id", sa.Text(), nullable=False),
        sa.Column("solutions_pages", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120",
            name=op.f("ck_assignment_title_length"),
        ),
        sa.CheckConstraint(
            "max_points > 0",
            name=op.f("ck_assignment_max_points_positive"),
        ),
        sa.CheckConstraint(
            "statement_pages >= 1",
            name=op.f("ck_assignment_statement_pages_positive"),
        ),
        sa.CheckConstraint(
            "solutions_pages >= 1",
            name=op.f("ck_assignment_solutions_pages_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_assignment_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_type_id"],
            ["gradebook.work_type.id"],
            name=op.f("fk_assignment_work_type_id_work_type"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["gradebook.grade_item.id"],
            name=op.f("fk_assignment_item_id_grade_item"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("bdz_id", name=op.f("pk_assignment")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        "task",
        sa.Column("bdz_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("max_points", sa.Numeric(6, 2), nullable=False),
        sa.CheckConstraint(
            "number BETWEEN 1 AND 50",
            name=op.f("ck_task_number_in_range"),
        ),
        sa.CheckConstraint("max_points > 0", name=op.f("ck_task_max_points_positive")),
        sa.ForeignKeyConstraint(
            ["bdz_id"],
            [f"{SCHEMA}.assignment.bdz_id"],
            name=op.f("fk_task_bdz_id_assignment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bdz_id", "number", name=op.f("pk_task")),
        schema=SCHEMA,
    )
    _ = op.create_table(
        "submission",
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("bdz_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("tg_file_id", sa.Text(), nullable=False),
        sa.Column("tg_file_unique_id", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status IN ('live', 'superseded')",
            name=op.f("ck_submission_status_known"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_submission_version_positive")),
        sa.CheckConstraint("pages >= 1", name=op.f("ck_submission_pages_positive")),
        sa.ForeignKeyConstraint(
            ["bdz_id"],
            [f"{SCHEMA}.assignment.bdz_id"],
            name=op.f("fk_submission_bdz_id_assignment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_submission_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("submission_id", name=op.f("pk_submission")),
        sa.UniqueConstraint(
            "bdz_id",
            "student_id",
            "version",
            name=op.f("uq_submission_version"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_submission_one_live",
        "submission",
        ["bdz_id", "student_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'live'"),
    )
    op.create_index(
        "ix_submission_bdz_status",
        "submission",
        ["bdz_id", "status"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Revert the revision."""
    op.drop_index("ix_submission_bdz_status", table_name="submission", schema=SCHEMA)
    op.drop_index("uq_submission_one_live", table_name="submission", schema=SCHEMA)
    op.drop_table("submission", schema=SCHEMA)
    op.drop_table("task", schema=SCHEMA)
    op.drop_table("assignment", schema=SCHEMA)
    drop_schema(SCHEMA)
