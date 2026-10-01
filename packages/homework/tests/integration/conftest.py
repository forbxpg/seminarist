"""Integration fixtures: the database, the roster, the ledger and homework."""

from __future__ import annotations

from gradebook_kit import gradebook
from homework_kit import homework
from notifications_kit import notifications
from roster_kit import roster
from smr_database import database_url, session

__all__ = (
    "database_url",
    "gradebook",
    "homework",
    "notifications",
    "roster",
    "session",
)
