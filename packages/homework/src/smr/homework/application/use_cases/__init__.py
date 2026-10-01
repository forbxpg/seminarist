"""What the teacher and the students do with homework."""

from __future__ import annotations

from ._assignments import (
    AssignmentDraft,
    AssignmentRoster,
    AssignmentSummary,
    CopyAssignment,
    CreateAssignment,
    DeleteAssignment,
    ListAssignments,
    UpdateAssignment,
)
from ._files import DeleteGroupFiles, DeleteStudentFiles, ExportSubmissions
from ._reminders import QueueReminders
from ._review import GradeSubmission, OpenSubmission, Review, ReviewQueue
from ._student import (
    AddFile,
    ClearDraft,
    MyWork,
    StudentAssignments,
    StudentWork,
    Submit,
)
from ._upload import Upload

__all__ = (
    "AddFile",
    "AssignmentDraft",
    "AssignmentRoster",
    "AssignmentSummary",
    "ClearDraft",
    "CopyAssignment",
    "CreateAssignment",
    "DeleteAssignment",
    "DeleteGroupFiles",
    "DeleteStudentFiles",
    "ExportSubmissions",
    "GradeSubmission",
    "ListAssignments",
    "MyWork",
    "OpenSubmission",
    "QueueReminders",
    "Review",
    "ReviewQueue",
    "StudentAssignments",
    "StudentWork",
    "Submit",
    "UpdateAssignment",
    "Upload",
)
