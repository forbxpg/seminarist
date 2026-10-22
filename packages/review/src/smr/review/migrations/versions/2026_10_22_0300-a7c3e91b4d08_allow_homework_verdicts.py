"""Let a verdict name ordinary homework as well as a БДЗ.

Revision ID: a7c3e91b4d08
Revises: 8d2f4a6c1e93
Create Date: 2026-10-22 03:00:00

"""

from __future__ import annotations

from alembic import op

from smr.review.infrastructure.models import SCHEMA

revision = "a7c3e91b4d08"
down_revision = "8d2f4a6c1e93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    op.drop_constraint(
        op.f("ck_verdict_source_known"),
        "verdict",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_verdict_source_known"),
        "verdict",
        "source IN ('bdz', 'homework')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision; fails while a homework verdict exists."""
    op.drop_constraint(
        op.f("ck_verdict_source_known"),
        "verdict",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_verdict_source_known"),
        "verdict",
        "source IN ('bdz')",
        schema=SCHEMA,
    )
