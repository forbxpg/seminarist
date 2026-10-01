"""The rules of homework."""

from __future__ import annotations

from ._entities import (
    Assignment,
    StatementFile,
    Submission,
    SubmissionFile,
    SubmissionStatus,
)
from ._errors import (
    AssignmentNotFoundError,
    DraftEmptyError,
    HomeworkError,
    NotYourAssignmentError,
    SubmissionClosedError,
    SubmissionNotFoundError,
    TooManyFilesError,
)
from ._folders import folder_name

__all__ = (
    "Assignment",
    "AssignmentNotFoundError",
    "DraftEmptyError",
    "HomeworkError",
    "NotYourAssignmentError",
    "StatementFile",
    "Submission",
    "SubmissionClosedError",
    "SubmissionFile",
    "SubmissionNotFoundError",
    "SubmissionStatus",
    "TooManyFilesError",
    "folder_name",
)
