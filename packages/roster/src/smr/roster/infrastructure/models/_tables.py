"""Names of the roster's schema, tables and constraints: the models' and revisions'."""

from __future__ import annotations

SCHEMA = "roster"

GROUP = "study_group"
GROUP_INVITE_UNIQUE = f"uq_{GROUP}_invite_code"

STUDENT = "student"
STUDENT_NAME_UNIQUE = f"uq_{STUDENT}_group_id_full_name"
STUDENT_ACCOUNT_UNIQUE = f"uq_{STUDENT}_group_id_tg_user_id"
STUDENT_JOURNAL_UNIQUE = f"uq_{STUDENT}_group_id_journal_no"
