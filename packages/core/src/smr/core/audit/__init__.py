"""Append-only audit log: who changed what, before and after."""

from __future__ import annotations

from ._entry import ActorKind, AuditEntry
from ._port import AuditLog
from ._sqlalchemy import SqlAlchemyAuditLog
from ._table import AUDIT_LOG_TABLE, AUDIT_METADATA
from ._tables import (
    APPEND_ONLY_FUNCTION,
    APPEND_ONLY_TRIGGER,
    APPEND_ONLY_TRUNCATE_TRIGGER,
    AUDIT_LOG_TABLE_NAME,
    AUDIT_SCHEMA_NAME,
    QUALIFIED_AUDIT_LOG_TABLE_NAME,
)

__all__ = (
    "APPEND_ONLY_FUNCTION",
    "APPEND_ONLY_TRIGGER",
    "APPEND_ONLY_TRUNCATE_TRIGGER",
    "AUDIT_LOG_TABLE",
    "AUDIT_LOG_TABLE_NAME",
    "AUDIT_METADATA",
    "AUDIT_SCHEMA_NAME",
    "QUALIFIED_AUDIT_LOG_TABLE_NAME",
    "ActorKind",
    "AuditEntry",
    "AuditLog",
    "SqlAlchemyAuditLog",
)
