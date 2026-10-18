"""Statuses of a verdict and of an appeal."""

from __future__ import annotations

from enum import StrEnum


class VerdictStatus(StrEnum):
    """Where a verdict is in its life."""

    PUBLISHED = "published"
    MANUAL = "manual"
    APPEALED = "appealed"
    SUPERSEDED = "superseded"
    FINAL = "final"
    VOIDED = "voided"


CURRENT_STATUSES: frozenset[VerdictStatus] = frozenset(
    {
        VerdictStatus.PUBLISHED,
        VerdictStatus.MANUAL,
        VerdictStatus.APPEALED,
        VerdictStatus.FINAL,
    },
)


class GraderKind(StrEnum):
    """Who wrote a verdict."""

    AGENT = "agent"
    TEACHER = "teacher"


class AppealStatus(StrEnum):
    """Whether an appeal is still open."""

    OPEN = "open"
    RESOLVED = "resolved"
