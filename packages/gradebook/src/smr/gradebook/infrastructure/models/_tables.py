"""Names of the ledger's schema, tables and constraints."""

from __future__ import annotations

SCHEMA = "gradebook"

WORK_TYPE = "work_type"
WORK_TYPE_SINGLE_KIND = f"uq_{WORK_TYPE}_group_id_single_kind"

ITEM = "grade_item"

ENTRY = "grade_entry"
ENTRY_ITEM_UNIQUE = f"uq_{ENTRY}_student_id_item_id"
