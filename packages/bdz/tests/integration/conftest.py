"""Integration fixtures for a БДЗ."""

from __future__ import annotations

from bdz_kit import bdz
from gradebook_kit import gradebook
from notifications_kit import notifications
from roster_kit import roster
from smr_database import database_url, session

__all__ = (
    "bdz",
    "database_url",
    "gradebook",
    "notifications",
    "roster",
    "session",
)
