"""Integration fixtures: the database, the roster and notifications."""

from __future__ import annotations

from notifications_kit import notifications
from roster_kit import roster
from smr_database import database_url, session

__all__ = ("database_url", "notifications", "roster", "session")
