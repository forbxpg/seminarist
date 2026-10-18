"""What other packages may do with verdicts, without reading the tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.review.domain import Verdict


class ReviewApi(Protocol):
    """Appeals, voids and the current verdict, for the package that owns the work."""

    async def has_open_appeal(self, source: str, work_id: uuid.UUID) -> bool:
        """Tell whether the live version has an open appeal.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.

        Returns:
            bool - True when its current verdict has an open appeal.

        """
        ...

    async def void(self, source: str, work_id: uuid.UUID) -> None:
        """Drop the current verdict because a new version arrived.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version being replaced.

        """
        ...

    async def current(self, source: str, work_id: uuid.UUID) -> Verdict | None:
        """Read the current verdict.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.

        Returns:
            Verdict | None - None when there is none.

        """
        ...

    async def forget_works(
        self,
        source: str,
        work_ids: Sequence[uuid.UUID],
    ) -> None:
        """Delete every verdict of these versions.

        Args:
            source: str - Which kind of work.
            work_ids: Sequence[uuid.UUID] - The versions.

        """
        ...
