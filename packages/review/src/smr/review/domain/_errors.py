"""What a review can refuse."""

from __future__ import annotations

from typing import Literal

AppealReason = Literal[
    "not_published",
    "already_appealed",
    "too_late",
    "teacher_final",
]


class ReviewError(Exception):
    """Base of the review's errors."""


class VerdictRejectedError(ReviewError):
    """A verdict failed a check the agent can correct.

    Attributes:
        reason: str - What to fix, in English.

    """

    def __init__(self, reason: str) -> None:
        self.reason: str = reason
        super().__init__(reason)


class StaleWorkError(ReviewError):
    """The work is gone, replaced, or its file changed."""


class AlreadyReviewedError(ReviewError):
    """The work already has a current verdict."""


class NotYourWorkError(ReviewError):
    """The account does not own the work."""


class AppealNotAllowedError(ReviewError):
    """An appeal cannot be filed.

    Attributes:
        reason: AppealReason - Why.

    """

    def __init__(self, reason: AppealReason) -> None:
        self.reason: AppealReason = reason
        super().__init__(reason)


class AppealTextError(ReviewError):
    """The appeal text is shorter than 10 or longer than 2000 characters."""


class AppealOpenError(ReviewError):
    """A new version cannot arrive while an appeal is open."""


class VerdictNotFoundError(ReviewError):
    """There is no such verdict."""


class UnknownSourceError(ReviewError):
    """The source named in a key is not wired, or the key is malformed."""
