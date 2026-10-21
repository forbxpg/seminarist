"""Students get their number in the group's journal.

Revision ID: 5b1e9c3d7a20
Revises: c4e8a1b07d55
Create Date: 2026-10-22 02:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.roster.infrastructure.models import SCHEMA

revision = "5b1e9c3d7a20"
down_revision = "c4e8a1b07d55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    op.add_column(
        "student",
        sa.Column(
            "journal_no",
            sa.Integer(),
            nullable=True,
            comment="Number in the group's journal; personal variants follow it",
        ),
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        op.f("uq_student_group_id_journal_no"),
        "student",
        ["group_id", "journal_no"],
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_student_journal_no_range"),
        "student",
        "journal_no BETWEEN 1 AND 999",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_constraint(op.f("ck_student_journal_no_range"), "student", schema=SCHEMA)
    op.drop_constraint(op.f("uq_student_group_id_journal_no"), "student", schema=SCHEMA)
    op.drop_column("student", "journal_no", schema=SCHEMA)
