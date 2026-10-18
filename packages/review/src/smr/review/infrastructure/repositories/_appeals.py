"""Appeals over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smr.review.domain import Appeal, AppealStatus
from smr.review.infrastructure.models import AppealModel


@final
class SqlAlchemyAppeals:
    """`AppealRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, appeal: Appeal) -> None:
        """Store an appeal.

        Args:
            appeal: Appeal - It.

        """
        self._session.add(
            AppealModel(
                appeal_id=appeal.appeal_id,
                verdict_id=appeal.verdict_id,
                body=appeal.text,
                status=appeal.status.value,
                filed_at=appeal.filed_at,
                resolved_at=appeal.resolved_at,
                resolution_verdict_id=appeal.resolution_verdict_id,
            ),
        )
        await self._session.flush()

    async def of_verdict(self, verdict_id: uuid.UUID) -> Appeal | None:
        """Read the appeal of a verdict.

        Args:
            verdict_id: uuid.UUID - The verdict.

        Returns:
            Appeal | None - None when it has none.

        """
        row = await self._session.scalar(
            select(AppealModel).where(AppealModel.verdict_id == verdict_id),
        )
        return None if row is None else _appeal(row)

    async def open(self) -> Sequence[Appeal]:
        """List open appeals, oldest first.

        Returns:
            Sequence[Appeal] - Them.

        """
        rows = await self._session.scalars(
            select(AppealModel)
            .where(AppealModel.status == AppealStatus.OPEN.value)
            .order_by(AppealModel.filed_at),
        )
        return [_appeal(row) for row in rows]

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
        row = await self._session.get(AppealModel, appeal_id)
        if row is None:
            return
        row.status = AppealStatus.RESOLVED.value
        row.resolution_verdict_id = resolution_verdict_id
        row.resolved_at = at


def _appeal(row: AppealModel) -> Appeal:
    return Appeal(
        appeal_id=row.appeal_id,
        verdict_id=row.verdict_id,
        text=row.body,
        status=AppealStatus(row.status),
        filed_at=row.filed_at,
        resolved_at=row.resolved_at,
        resolution_verdict_id=row.resolution_verdict_id,
    )
