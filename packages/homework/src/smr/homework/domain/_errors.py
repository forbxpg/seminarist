"""Errors of homework."""

from __future__ import annotations


class HomeworkError(Exception):
    """Base of homework's errors."""


class AssignmentNotFoundError(HomeworkError):
    """No such assignment."""


class NotYourAssignmentError(HomeworkError):
    """The account holds no approved row of the assignment's group."""


class SubmissionNotFoundError(HomeworkError):
    """No such submission."""


class SubmissionClosedError(HomeworkError):
    """The work is graded: it can no longer be replaced."""


class DraftEmptyError(HomeworkError):
    """There is nothing in the draft to submit."""


class TooManyFilesError(HomeworkError):
    """The draft already holds as many files as allowed."""
