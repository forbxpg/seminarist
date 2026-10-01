"""Create the notifications schema: the outbox and the preferences.

Revision ID: b09c63eb4201
Revises: 9fb6a69b208f
Create Date: 2026-10-02 01:50:20.211834

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from smr.migrator.ops import create_schema, drop_schema
from smr.notifications.infrastructure.models import SCHEMA

revision = "b09c63eb4201"
down_revision = "9fb6a69b208f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "outbox",
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "gave_up",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name=op.f("ck_outbox_payload_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
        sa.UniqueConstraint("dedupe_key", name="uq_outbox_dedupe_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_outbox_waiting",
        "outbox",
        ["id"],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("sent_at IS NULL AND NOT gave_up"),
    )
    _ = op.create_table(
        "preference",
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column(
            "reminders",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_preference_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("student_id", name=op.f("pk_preference")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table("preference", schema=SCHEMA)
    op.drop_index(
        "ix_outbox_waiting",
        table_name="outbox",
        schema=SCHEMA,
        postgresql_where=sa.text("sent_at IS NULL AND NOT gave_up"),
    )
    op.drop_table("outbox", schema=SCHEMA)
    drop_schema(SCHEMA)
