"""Where verdicts and appeals are kept."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- protocol method
from collections.abc import Sequence  # ruff: ignore[typing-only-standard-library-import] -- protocol method
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- protocol method
from typing import Protocol

from smr.review.domain import (  # ruff: ignore[typing-only-first-party-import] -- protocol method
    Appeal,
    Verdict,
    VerdictStatus,
)


class VerdictRepository(Protocol):
    """Stored verdicts."""

    async def add(self, verdict: Verdict) -> None:
        """Store a verdict and its tasks.

        Args:
            verdict: Verdict - It.

        """
        ...

    async def current(
        self,
        source: str,
        work_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Verdict | None:
        """Read the current verdict of a version.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.
            lock: bool - Lock the row when true.

        Returns:
            Verdict | None - None when there is no current verdict.

        """
        ...

    async def get(self, verdict_id: uuid.UUID) -> Verdict | None:
        """Read a verdict.

        Args:
            verdict_id: uuid.UUID - It.

        Returns:
            Verdict | None - None when unknown.

        """
        ...

    async def set_status(
        self,
        verdict_id: uuid.UUID,
        status: VerdictStatus,
        *,
        published_at: datetime | None = None,
    ) -> None:
        """Change a verdict's status.

        Args:
            verdict_id: uuid.UUID - It.
            status: VerdictStatus - The new status.
            published_at: datetime | None - Set when the student was told.

        """
        ...

    async def of_status(self, statuses: Sequence[VerdictStatus]) -> Sequence[Verdict]:
        """List verdicts of these statuses, oldest first.

        Args:
            statuses: Sequence[VerdictStatus] - Which ones.

        Returns:
            Sequence[Verdict] - The verdicts.

        """
        ...

    async def current_work_ids(self, source: str) -> set[uuid.UUID]:
        """Tell which versions already have a current verdict.

        Args:
            source: str - Which kind of work.

        Returns:
            set[uuid.UUID] - Their ids.

        """
        ...

    async def delete_of_works(
        self,
        source: str,
        work_ids: Sequence[uuid.UUID],
    ) -> None:
        """Delete the verdicts of these versions.

        Args:
            source: str - Which kind of work.
            work_ids: Sequence[uuid.UUID] - The versions.

        """
        ...


class AppealRepository(Protocol):
    """Stored appeals."""

    async def add(self, appeal: Appeal) -> None:
        """Store an appeal.

        Args:
            appeal: Appeal - It.

        """
        ...

    async def of_verdict(self, verdict_id: uuid.UUID) -> Appeal | None:
        """Read the appeal of a verdict.

        Args:
            verdict_id: uuid.UUID - The verdict.

        Returns:
            Appeal | None - None when it has none.

        """
        ...

    async def open(self) -> Sequence[Appeal]:
        """List open appeals, oldest first.

        Returns:
            Sequence[Appeal] - Them.

        """
        ...

    async def resolve(
        self,
        appeal_id: uuid.UUID,
        resolution_verdict_id: uuid.UUID,
        at: datetime,
    ) -> None:
        """Close an appeal with the teacher's verdict.

        Args:
            appeal_id: uuid.UUID - It.
            resolution_verdict_id: uuid.UUID - The teacher's verdict.
            at: datetime - When.

        """
        ...
