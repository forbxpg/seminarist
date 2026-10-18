"""Whether a version is the one the student currently stands by."""

from __future__ import annotations

from enum import StrEnum


class SubmissionStatus(StrEnum):
    """A version is live until a newer one replaces it."""

    LIVE = "live"
    SUPERSEDED = "superseded"
