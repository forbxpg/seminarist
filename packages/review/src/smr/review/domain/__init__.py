"""The rules of a verdict."""

from __future__ import annotations

from ._checks import (
    APPEAL_WINDOW,
    appeal_open_until,
    check_pages_seen,
    check_tasks,
    status_for,
)
from ._entities import Appeal, SchemeTask, TaskVerdict, Verdict
from ._enums import CURRENT_STATUSES, AppealStatus, GraderKind, VerdictStatus
from ._errors import (
    AlreadyReviewedError,
    AppealNotAllowedError,
    AppealOpenError,
    AppealTextError,
    NotYourWorkError,
    ReviewError,
    StaleWorkError,
    UnknownSourceError,
    VerdictNotFoundError,
    VerdictRejectedError,
)

__all__ = (
    "APPEAL_WINDOW",
    "CURRENT_STATUSES",
    "AlreadyReviewedError",
    "Appeal",
    "AppealNotAllowedError",
    "AppealOpenError",
    "AppealStatus",
    "AppealTextError",
    "GraderKind",
    "NotYourWorkError",
    "ReviewError",
    "SchemeTask",
    "StaleWorkError",
    "TaskVerdict",
    "UnknownSourceError",
    "Verdict",
    "VerdictNotFoundError",
    "VerdictRejectedError",
    "VerdictStatus",
    "appeal_open_until",
    "check_pages_seen",
    "check_tasks",
    "status_for",
)
