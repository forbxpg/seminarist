"""Audit log port."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ._entry import AuditEntry


class AuditLog(Protocol):
    """Where the audit entries are written."""

    async def record(self, entry: AuditEntry) -> None:
        """Record an entry in the current transaction.

        Args:
            entry: AuditEntry - The change.

        """
        ...
