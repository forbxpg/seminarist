"""ORM models of homework."""

from __future__ import annotations

from ._base import METADATA, HomeworkBase
from ._models import AssignmentModel, FileModel, SubmissionModel
from ._tables import (
    ASSIGNMENT,
    FILE,
    SCHEMA,
    SUBMISSION,
    SUBMISSION_ONE_DRAFT,
    SUBMISSION_ONE_LIVE,
)

__all__ = (
    "ASSIGNMENT",
    "FILE",
    "METADATA",
    "SCHEMA",
    "SUBMISSION",
    "SUBMISSION_ONE_DRAFT",
    "SUBMISSION_ONE_LIVE",
    "AssignmentModel",
    "FileModel",
    "HomeworkBase",
    "SubmissionModel",
)
