"""A БДЗ may come without a solutions PDF: the agent then solves the tasks itself.

Revision ID: 8d2f4a6c1e93
Revises: 5b1e9c3d7a20
Create Date: 2026-10-22 02:30:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.bdz.infrastructure.models import SCHEMA

revision = "8d2f4a6c1e93"
down_revision = "5b1e9c3d7a20"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("solutions_path", sa.Text()),
    ("solutions_tg_file_id", sa.Text()),
    ("solutions_pages", sa.Integer()),
)


def upgrade() -> None:
    """Apply the revision."""
    for name, kind in _COLUMNS:
        op.alter_column(
            "assignment",
            name,
            existing_type=kind,
            nullable=True,
            schema=SCHEMA,
        )
    op.create_check_constraint(
        op.f("ck_assignment_solutions_file_id_with_path"),
        "assignment",
        "(solutions_path IS NULL) = (solutions_tg_file_id IS NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        op.f("ck_assignment_solutions_pages_with_path"),
        "assignment",
        "(solutions_path IS NULL) = (solutions_pages IS NULL)",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision; fails while a БДЗ without solutions exists."""
    op.drop_constraint(
        op.f("ck_assignment_solutions_pages_with_path"),
        "assignment",
        schema=SCHEMA,
    )
    op.drop_constraint(
        op.f("ck_assignment_solutions_file_id_with_path"),
        "assignment",
        schema=SCHEMA,
    )
    for name, kind in _COLUMNS:
        op.alter_column(
            "assignment",
            name,
            existing_type=kind,
            nullable=False,
            schema=SCHEMA,
        )
