"""Create the review schema: verdicts, their tasks and appeals.

Revision ID: f3a91c0e7b44
Revises: ce87adb31c61
Create Date: 2026-10-18 19:10:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from smr.migrator.ops import create_schema, drop_schema
from smr.review.infrastructure.models import SCHEMA

revision = "f3a91c0e7b44"
down_revision = "ce87adb31c61"
branch_labels = None
depends_on = None

_STATUSES = "('published', 'manual', 'appealed', 'superseded', 'final', 'voided')"
_CURRENT = "('published', 'manual', 'appealed', 'final')"


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "verdict",
        sa.Column("verdict_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("work_id", sa.UUID(), nullable=False),
        sa.Column("work_sha256", sa.Text(), nullable=False),
        sa.Column("task_ref", sa.UUID(), nullable=False),
        sa.Column("student_ref", sa.UUID(), nullable=False),
        sa.Column("grader_kind", sa.Text(), nullable=False),
        sa.Column("grader", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_points", sa.Numeric(6, 2), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("pages_seen", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source IN ('bdz')", name=op.f("ck_verdict_source_known")),
        sa.CheckConstraint(
            f"status IN {_STATUSES}",
            name=op.f("ck_verdict_status_known"),
        ),
        sa.CheckConstraint(
            "grader_kind IN ('agent', 'teacher')",
            name=op.f("ck_verdict_grader_kind_known"),
        ),
        sa.CheckConstraint(
            "char_length(summary) <= 1000",
            name=op.f("ck_verdict_summary_length"),
        ),
        sa.CheckConstraint(
            "char_length(grader) BETWEEN 1 AND 64",
            name=op.f("ck_verdict_grader_length"),
        ),
        sa.CheckConstraint(
            "total >= 0 AND max_points > 0",
            name=op.f("ck_verdict_points_sane"),
        ),
        sa.CheckConstraint(
            "pages_seen >= 1",
            name=op.f("ck_verdict_pages_seen_positive"),
        ),
        sa.PrimaryKeyConstraint("verdict_id", name=op.f("pk_verdict")),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_verdict_one_current",
        "verdict",
        ["source", "work_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text(f"status IN {_CURRENT}"),
    )
    op.create_index(
        "ix_verdict_source_status",
        "verdict",
        ["source", "status"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "verdict_task",
        sa.Column("verdict_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("points", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_points", sa.Numeric(6, 2), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "unreadable",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "unsure",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "manipulation",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "pages",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{}'::integer[]"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "points >= 0 AND max_points > 0",
            name=op.f("ck_verdict_task_points_sane"),
        ),
        sa.CheckConstraint(
            "NOT manipulation OR points = 0",
            name=op.f("ck_verdict_task_manipulation_is_zero"),
        ),
        sa.CheckConstraint(
            "char_length(explanation) <= 1500",
            name=op.f("ck_verdict_task_explanation_length"),
        ),
        sa.ForeignKeyConstraint(
            ["verdict_id"],
            [f"{SCHEMA}.verdict.verdict_id"],
            name=op.f("fk_verdict_task_verdict_id_verdict"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "verdict_id",
            "number",
            name=op.f("pk_verdict_task"),
        ),
        schema=SCHEMA,
    )
    _ = op.create_table(
        "appeal",
        sa.Column("appeal_id", sa.UUID(), nullable=False),
        sa.Column("verdict_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_verdict_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name=op.f("ck_appeal_status_known"),
        ),
        sa.CheckConstraint(
            'char_length("text") BETWEEN 10 AND 2000',
            name=op.f("ck_appeal_text_length"),
        ),
        sa.ForeignKeyConstraint(
            ["verdict_id"],
            [f"{SCHEMA}.verdict.verdict_id"],
            name=op.f("fk_appeal_verdict_id_verdict"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolution_verdict_id"],
            [f"{SCHEMA}.verdict.verdict_id"],
            name=op.f("fk_appeal_resolution_verdict_id_verdict"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("appeal_id", name=op.f("pk_appeal")),
        sa.UniqueConstraint("verdict_id", name=op.f("uq_appeal_verdict_id")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Revert the revision."""
    op.drop_table("appeal", schema=SCHEMA)
    op.drop_table("verdict_task", schema=SCHEMA)
    op.drop_index("ix_verdict_source_status", table_name="verdict", schema=SCHEMA)
    op.drop_index("uq_verdict_one_current", table_name="verdict", schema=SCHEMA)
    op.drop_table("verdict", schema=SCHEMA)
    drop_schema(SCHEMA)
