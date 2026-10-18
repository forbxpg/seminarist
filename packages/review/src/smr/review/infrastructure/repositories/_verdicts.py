"""Verdicts over the session."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from smr.review.domain import (
    CURRENT_STATUSES,
    GraderKind,
    TaskVerdict,
    Verdict,
    VerdictStatus,
)
from smr.review.infrastructure.models import VerdictModel, VerdictTaskModel

_CURRENT = tuple(status.value for status in CURRENT_STATUSES)


@final
class SqlAlchemyVerdicts:
    """`VerdictRepository` in the session's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def add(self, verdict: Verdict) -> None:
        """Store a verdict and its tasks.

        Args:
            verdict: Verdict - It.

        """
        self._session.add(_row(verdict))
        for task in verdict.tasks:
            self._session.add(_task_row(verdict.verdict_id, task))
        await self._session.flush()

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
        query = select(VerdictModel).where(
            VerdictModel.source == source,
            VerdictModel.work_id == work_id,
            VerdictModel.status.in_(_CURRENT),
        )
        if lock:
            query = query.with_for_update()
        row = await self._session.scalar(query)
        return None if row is None else await self._load(row)

    async def get(self, verdict_id: uuid.UUID) -> Verdict | None:
        """Read a verdict.

        Args:
            verdict_id: uuid.UUID - It.

        Returns:
            Verdict | None - None when unknown.

        """
        row = await self._session.get(VerdictModel, verdict_id)
        return None if row is None else await self._load(row)

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
        row = await self._session.get(VerdictModel, verdict_id)
        if row is None:
            return
        row.status = status.value
        if published_at is not None:
            row.published_at = published_at

    async def of_status(self, statuses: Sequence[VerdictStatus]) -> Sequence[Verdict]:
        """List verdicts of these statuses, oldest first.

        Args:
            statuses: Sequence[VerdictStatus] - Which ones.

        Returns:
            Sequence[Verdict] - The verdicts.

        """
        wanted = [status.value for status in statuses]
        rows = await self._session.scalars(
            select(VerdictModel)
            .where(VerdictModel.status.in_(wanted))
            .order_by(VerdictModel.created_at),
        )
        return [await self._load(row) for row in rows]

    async def current_work_ids(self, source: str) -> set[uuid.UUID]:
        """Tell which versions already have a current verdict.

        Args:
            source: str - Which kind of work.

        Returns:
            set[uuid.UUID] - Their ids.

        """
        rows = await self._session.scalars(
            select(VerdictModel.work_id).where(
                VerdictModel.source == source,
                VerdictModel.status.in_(_CURRENT),
            ),
        )
        return set(rows.all())

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
        if not work_ids:
            return
        _ = await self._session.execute(
            delete(VerdictModel).where(
                VerdictModel.source == source,
                VerdictModel.work_id.in_(work_ids),
            ),
        )

    async def _load(self, row: VerdictModel) -> Verdict:
        tasks = await self._session.scalars(
            select(VerdictTaskModel)
            .where(VerdictTaskModel.verdict_id == row.verdict_id)
            .order_by(VerdictTaskModel.number),
        )
        return Verdict(
            verdict_id=row.verdict_id,
            source=row.source,
            work_id=row.work_id,
            work_sha256=row.work_sha256,
            task_ref=row.task_ref,
            student_ref=row.student_ref,
            grader_kind=GraderKind(row.grader_kind),
            grader=row.grader,
            status=VerdictStatus(row.status),
            total=row.total,
            max_points=row.max_points,
            summary=row.summary,
            pages_seen=row.pages_seen,
            created_at=row.created_at,
            published_at=row.published_at,
            tasks=tuple(_task(task) for task in tasks),
        )


def _row(verdict: Verdict) -> VerdictModel:
    return VerdictModel(
        verdict_id=verdict.verdict_id,
        source=verdict.source,
        work_id=verdict.work_id,
        work_sha256=verdict.work_sha256,
        task_ref=verdict.task_ref,
        student_ref=verdict.student_ref,
        grader_kind=verdict.grader_kind.value,
        grader=verdict.grader,
        status=verdict.status.value,
        total=verdict.total,
        max_points=verdict.max_points,
        summary=verdict.summary,
        pages_seen=verdict.pages_seen,
        created_at=verdict.created_at,
        published_at=verdict.published_at,
    )


def _task_row(verdict_id: uuid.UUID, task: TaskVerdict) -> VerdictTaskModel:
    return VerdictTaskModel(
        verdict_id=verdict_id,
        number=task.number,
        points=task.points,
        max_points=task.max_points,
        explanation=task.explanation.strip(),
        unreadable=task.unreadable,
        unsure=task.unsure,
        manipulation=task.manipulation,
        pages=list(task.pages),
    )


def _task(row: VerdictTaskModel) -> TaskVerdict:
    return TaskVerdict(
        number=row.number,
        points=row.points,
        max_points=row.max_points,
        explanation=row.explanation,
        unreadable=row.unreadable,
        unsure=row.unsure,
        manipulation=row.manipulation,
        pages=tuple(row.pages),
    )
