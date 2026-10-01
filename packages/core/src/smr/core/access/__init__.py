"""Who may act as a teacher: checked in the use cases, not only in the interface."""

from __future__ import annotations

from ._guard import AdminGuard, NotAdminError

__all__ = ("AdminGuard", "NotAdminError")
