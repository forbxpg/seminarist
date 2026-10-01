"""Create the append-only audit log.

Revision ID: c0a0d1700001
Revises:
Create Date: 2026-10-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from smr.core.audit import (
    APPEND_ONLY_FUNCTION,
    APPEND_ONLY_TRIGGER,
    APPEND_ONLY_TRUNCATE_TRIGGER,
    AUDIT_LOG_TABLE_NAME,
    AUDIT_SCHEMA_NAME,
    QUALIFIED_AUDIT_LOG_TABLE_NAME,
)
from smr.migrator.ops import create_schema, drop_schema

revision = "c0a0d1700001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(AUDIT_SCHEMA_NAME)
    _ = op.create_table(
        AUDIT_LOG_TABLE_NAME,
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
            comment="Record number",
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When it happened",
        ),
        sa.Column(
            "actor_kind",
            sa.Text(),
            nullable=False,
            comment="admin, student or system",
        ),
        sa.Column(
            "actor_id",
            sa.Text(),
            nullable=True,
            comment="Telegram id or roster id",
        ),
        sa.Column("action", sa.Text(), nullable=False, comment="What happened"),
        sa.Column(
            "entity",
            sa.Text(),
            nullable=False,
            comment="Kind of the changed thing",
        ),
        sa.Column("entity_id", sa.Text(), nullable=False, comment="Its id"),
        sa.Column(
            "before",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Fields before; none on creation",
        ),
        sa.Column(
            "after",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Fields after; none on deletion",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log")),
        schema=AUDIT_SCHEMA_NAME,
    )
    # A correction is a new record: the triggers refuse to rewrite or erase the log.
    op.execute(
        f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit log is append-only: % refused', TG_OP;
        END;
        $$
        """,
    )
    op.execute(
        f"""
        CREATE TRIGGER {APPEND_ONLY_TRIGGER}
        BEFORE UPDATE OR DELETE ON {QUALIFIED_AUDIT_LOG_TABLE_NAME}
        FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()
        """,
    )
    op.execute(
        f"""
        CREATE TRIGGER {APPEND_ONLY_TRUNCATE_TRIGGER}
        BEFORE TRUNCATE ON {QUALIFIED_AUDIT_LOG_TABLE_NAME}
        FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()
        """,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_table(AUDIT_LOG_TABLE_NAME, schema=AUDIT_SCHEMA_NAME)
    op.execute(f"DROP FUNCTION {APPEND_ONLY_FUNCTION}()")
    drop_schema(AUDIT_SCHEMA_NAME)
