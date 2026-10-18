"""ORM models of a БДЗ."""

from __future__ import annotations

from ._base import METADATA, BdzBase
from ._models import AssignmentModel, SubmissionModel, TaskModel
from ._tables import ASSIGNMENT, SCHEMA, SUBMISSION, SUBMISSION_ONE_LIVE, TASK

__all__ = (
    "ASSIGNMENT",
    "METADATA",
    "SCHEMA",
    "SUBMISSION",
    "SUBMISSION_ONE_LIVE",
    "TASK",
    "AssignmentModel",
    "BdzBase",
    "SubmissionModel",
    "TaskModel",
)
