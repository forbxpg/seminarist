"""Names of homework's schema, tables and constraints."""

from __future__ import annotations

SCHEMA = "homework"
ASSIGNMENT = "assignment"
SUBMISSION = "submission"
SUBMISSION_ONE_DRAFT = f"uq_{SUBMISSION}_one_draft"
SUBMISSION_ONE_LIVE = f"uq_{SUBMISSION}_one_live"
FILE = "submission_file"
