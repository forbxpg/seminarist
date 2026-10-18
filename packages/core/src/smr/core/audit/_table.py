"""Audit log table."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Identity,
    MetaData,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from smr.core.database import make_metadata

from ._tables import AUDIT_LOG_TABLE_NAME, AUDIT_SCHEMA_NAME

AUDIT_METADATA: MetaData = make_metadata(AUDIT_SCHEMA_NAME)

AUDIT_LOG_TABLE = Table(
    AUDIT_LOG_TABLE_NAME,
    AUDIT_METADATA,
    Column("id", BigInteger, Identity(), primary_key=True, comment="Record number"),
    Column(
        "occurred_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When it happened",
    ),
    Column(
        "actor_kind",
        Text,
        nullable=False,
        comment="admin, student, system or agent",
    ),
    Column("actor_id", Text, nullable=True, comment="Telegram id or roster id"),
    Column("action", Text, nullable=False, comment="What happened"),
    Column("entity", Text, nullable=False, comment="Kind of the changed thing"),
    Column("entity_id", Text, nullable=False, comment="Its id"),
    Column("before", JSONB, nullable=True, comment="Fields before; none on creation"),
    Column("after", JSONB, nullable=True, comment="Fields after; none on deletion"),
)
