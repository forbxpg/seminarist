"""Create the roster schema: groups and their rosters.

Revision ID: 8fd5d770bd7c
Revises: c0a0d1700001
Create Date: 2026-10-02 01:24:08.328001

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.migrator.ops import create_schema, drop_schema
from smr.roster.infrastructure.models import SCHEMA

revision = "8fd5d770bd7c"
down_revision = "c0a0d1700001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "study_group",
        sa.Column("title", sa.Text(), nullable=False, comment="Study group"),
        sa.Column("subject", sa.Text(), nullable=False, comment="Subject"),
        sa.Column("semester", sa.Text(), nullable=False, comment="Semester"),
        sa.Column(
            "invite_code",
            sa.Text(),
            nullable=False,
            comment="Payload of the join link",
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reminder_hours",
            sa.Integer(),
            server_default=sa.text("24"),
            nullable=False,
        ),
        sa.Column(
            "board_weight",
            sa.Float(),
            server_default=sa.text("1.0"),
            nullable=False,
        ),
        sa.Column(
            "score_weight",
            sa.Float(),
            server_default=sa.text("1.0"),
            nullable=False,
        ),
        sa.Column(
            "retention_days",
            sa.Integer(),
            server_default=sa.text("180"),
            nullable=False,
        ),
        sa.Column(
            "show_rank",
            sa.Boolean(),
            server_default=sa.text("true"),
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
            "(status = 'archived') = (archived_at IS NOT NULL)",
            name=op.f("ck_study_group_archived_at_iff_archived"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name=op.f("ck_study_group_status_known"),
        ),
        sa.CheckConstraint(
            "board_weight >= 0 AND score_weight >= 0",
            name=op.f("ck_study_group_weights_positive"),
        ),
        sa.CheckConstraint(
            "reminder_hours BETWEEN 1 AND 168",
            name=op.f("ck_study_group_reminder_hours_range"),
        ),
        sa.CheckConstraint(
            "retention_days BETWEEN 1 AND 3650",
            name=op.f("ck_study_group_retention_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_group")),
        sa.UniqueConstraint("invite_code", name="uq_study_group_invite_code"),
        schema=SCHEMA,
    )
    _ = op.create_table(
        "student",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column(
            "full_name",
            sa.Text(),
            nullable=False,
            comment="As the teacher typed it",
        ),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "binding",
            sa.Text(),
            server_default=sa.text("'unbound'"),
            nullable=False,
        ),
        sa.Column("binding_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_version", sa.Text(), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
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
            "(binding = 'unbound') = (tg_user_id IS NULL)",
            name=op.f("ck_student_account_iff_claimed"),
        ),
        sa.CheckConstraint(
            "binding IN ('unbound', 'pending', 'bound')",
            name=op.f("ck_student_binding_known"),
        ),
        sa.CheckConstraint(
            "char_length(full_name) BETWEEN 1 AND 200",
            name=op.f("ck_student_name_length"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_student_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student")),
        sa.UniqueConstraint(
            "group_id",
            "full_name",
            name="uq_student_group_id_full_name",
        ),
        sa.UniqueConstraint(
            "group_id",
            "tg_user_id",
            name="uq_student_group_id_tg_user_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_roster_student_group_id"),
        "student",
        ["group_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_roster_student_tg_user_id"),
        "student",
        ["tg_user_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_index(
        op.f("ix_roster_student_tg_user_id"),
        table_name="student",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_roster_student_group_id"),
        table_name="student",
        schema=SCHEMA,
    )
    op.drop_table("student", schema=SCHEMA)
    op.drop_table("study_group", schema=SCHEMA)
    drop_schema(SCHEMA)
