"""Create the sessions schema: sessions, attendance and board calls.

Revision ID: a36a192fd3e6
Revises: fb607d6a7001
Create Date: 2026-10-02 01:38:22.268298

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from smr.migrator.ops import create_schema, drop_schema
from smr.sessions.infrastructure.models import SCHEMA

revision = "a36a192fd3e6"
down_revision = "fb607d6a7001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the revision."""
    create_schema(SCHEMA)
    _ = op.create_table(
        "seminar_session",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("attendance_item_id", sa.UUID(), nullable=True),
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
            "char_length(topic) BETWEEN 1 AND 200",
            name=op.f("ck_seminar_session_topic_length"),
        ),
        sa.ForeignKeyConstraint(
            ["attendance_item_id"],
            ["gradebook.grade_item.id"],
            name=op.f("fk_seminar_session_attendance_item_id_grade_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["roster.study_group.id"],
            name=op.f("fk_seminar_session_group_id_study_group"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seminar_session")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_sessions_seminar_session_group_id"),
        "seminar_session",
        ["group_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "attendance",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('present', 'absent', 'excused')",
            name=op.f("ck_attendance_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.seminar_session.id"],
            name=op.f("fk_attendance_session_id_seminar_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_attendance_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", "student_id", name=op.f("pk_attendance")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_sessions_attendance_student_id"),
        "attendance",
        ["student_id"],
        unique=False,
        schema=SCHEMA,
    )
    _ = op.create_table(
        "board_call",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("entry_id", sa.UUID(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mode IN ('manual', 'random')",
            name=op.f("ck_board_call_mode_known"),
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["gradebook.grade_entry.id"],
            name=op.f("fk_board_call_entry_id_grade_entry"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.seminar_session.id"],
            name=op.f("fk_board_call_session_id_seminar_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["roster.student.id"],
            name=op.f("fk_board_call_student_id_student"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_call")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_sessions_board_call_session_id"),
        "board_call",
        ["session_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_sessions_board_call_student_id"),
        "board_call",
        ["student_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Undo the revision."""
    op.drop_index(
        op.f("ix_sessions_board_call_student_id"),
        table_name="board_call",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_sessions_board_call_session_id"),
        table_name="board_call",
        schema=SCHEMA,
    )
    op.drop_table("board_call", schema=SCHEMA)
    op.drop_index(
        op.f("ix_sessions_attendance_student_id"),
        table_name="attendance",
        schema=SCHEMA,
    )
    op.drop_table("attendance", schema=SCHEMA)
    op.drop_index(
        op.f("ix_sessions_seminar_session_group_id"),
        table_name="seminar_session",
        schema=SCHEMA,
    )
    op.drop_table("seminar_session", schema=SCHEMA)
    drop_schema(SCHEMA)
