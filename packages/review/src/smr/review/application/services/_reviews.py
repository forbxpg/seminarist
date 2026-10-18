"""`ReviewApi`: appeals, voids and deletion. It never commits."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import final

from smr.review.application.ports import AppealRepository, VerdictRepository
from smr.review.domain import AppealStatus, Verdict, VerdictStatus


@final
class Reviews:
    """`ReviewApi` in the caller's transaction."""

    def __init__(
        self,
        verdicts: VerdictRepository,
        appeals: AppealRepository,
    ) -> None:
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals

    async def has_open_appeal(self, source: str, work_id: uuid.UUID) -> bool:
        """Tell whether the live version has an open appeal.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.

        Returns:
            bool - True when its current verdict has an open appeal.

        """
        current = await self._verdicts.current(source, work_id)
        if current is None:
            return False
        appeal = await self._appeals.of_verdict(current.verdict_id)
        return appeal is not None and appeal.status is AppealStatus.OPEN

    async def void(self, source: str, work_id: uuid.UUID) -> None:
        """Drop the current verdict because a new version arrived.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version being replaced.

        """
        current = await self._verdicts.current(source, work_id)
        if current is None:
            return
        await self._verdicts.set_status(current.verdict_id, VerdictStatus.VOIDED)

    async def current(self, source: str, work_id: uuid.UUID) -> Verdict | None:
        """Read the current verdict.

        Args:
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.

        Returns:
            Verdict | None - None when there is none.

        """
        return await self._verdicts.current(source, work_id)

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
        await self._verdicts.delete_of_works(source, work_ids)
