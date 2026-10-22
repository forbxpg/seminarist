"""A student's own verdict and appeal."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import final

from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.notifications.application.contracts import NotificationsApi
from smr.notifications.domain import NotificationKind
from smr.review.application.ports import (
    AppealRepository,
    ReviewSource,
    VerdictRepository,
)
from smr.review.domain import (
    Appeal,
    AppealNotAllowedError,
    AppealStatus,
    AppealTextError,
    NotYourWorkError,
    StaleWorkError,
    Verdict,
    VerdictStatus,
    appeal_open_until,
)

from ._keys import source_of

_TEXT_MIN = 10
_TEXT_MAX = 2000


@dataclass(frozen=True, slots=True)
class VerdictView:
    """What a student may see of a verdict.

    Attributes:
        verdict: Verdict - The current one.
        can_appeal: bool - Whether an appeal can still be filed.
        appeal_until: datetime | None - The deadline, when the grade was published.
        appeal: Appeal | None - The appeal, if one was filed.

    """

    verdict: Verdict
    can_appeal: bool
    appeal_until: datetime | None
    appeal: Appeal | None


@final
class MyVerdict:
    """The student's own current verdict."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        appeals: AppealRepository,
        clock: Clock,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals
        self._clock: Clock = clock

    async def __call__(
        self,
        tg_user_id: int,
        source: str,
        work_id: uuid.UUID,
    ) -> VerdictView | None:
        """Read it.

        Args:
            tg_user_id: int - The account.
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.

        Returns:
            VerdictView | None - None when there is no current verdict.

        Raises:
            NotYourWorkError: If the account does not own the version.

        """
        origin = source_of(self._sources, source)
        if not await origin.belongs_to(work_id, tg_user_id):
            raise NotYourWorkError
        verdict = await self._verdicts.current(source, work_id)
        if verdict is None:
            return None
        appeal = await self._appeals.of_verdict(verdict.verdict_id)
        until = (
            None
            if verdict.published_at is None
            else appeal_open_until(verdict.published_at)
        )
        open_now = until is not None and self._clock.now() <= until
        can_appeal = (
            verdict.status is VerdictStatus.PUBLISHED and appeal is None and open_now
        )
        return VerdictView(verdict, can_appeal, until, appeal)


@final
class FileAppeal:
    """A student disputes an agent's published grade."""

    def __init__(
        self,
        sources: Sequence[ReviewSource],
        verdicts: VerdictRepository,
        appeals: AppealRepository,
        notifications: NotificationsApi,
        audit: AuditLog,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._sources: Sequence[ReviewSource] = sources
        self._verdicts: VerdictRepository = verdicts
        self._appeals: AppealRepository = appeals
        self._notifications: NotificationsApi = notifications
        self._audit: AuditLog = audit
        self._uow: UnitOfWork = uow
        self._clock: Clock = clock

    async def __call__(
        self,
        tg_user_id: int,
        source: str,
        work_id: uuid.UUID,
        text: str,
    ) -> Appeal:
        """File it.

        Args:
            tg_user_id: int - The account.
            source: str - Which kind of work.
            work_id: uuid.UUID - The version.
            text: str - What the student disagrees with.

        Returns:
            Appeal - The filed appeal.

        Raises:
            NotYourWorkError: If the account does not own the version.
            AppealTextError: If the text is outside 10..2000 characters.
            AppealNotAllowedError: If the verdict cannot be appealed.
            StaleWorkError: If the version is no longer live.

        """
        origin = source_of(self._sources, source)
        if not await origin.belongs_to(work_id, tg_user_id):
            raise NotYourWorkError
        clean = " ".join(text.split())
        if not _TEXT_MIN <= len(clean) <= _TEXT_MAX:
            raise AppealTextError
        async with self._uow:
            work = await origin.work(work_id, lock=True)
            if work is None:
                raise StaleWorkError
            verdict = await self._verdicts.current(source, work_id, lock=True)
            await self._refuse_unless_open(verdict)
            if verdict is None:
                reason = "not_published"
                raise AppealNotAllowedError(reason)
            filed = Appeal(
                appeal_id=uuid.uuid4(),
                verdict_id=verdict.verdict_id,
                text=clean,
                status=AppealStatus.OPEN,
                filed_at=self._clock.now(),
                resolved_at=None,
                resolution_verdict_id=None,
            )
            await self._verdicts.set_status(verdict.verdict_id, VerdictStatus.APPEALED)
            await self._appeals.add(filed)
            payload: dict[str, object] = {
                "title": work.title,
                "work_no": verdict.verdict_id.hex[:8],
            }
            if origin.name == "homework":
                payload["label"] = "домашнее задание"
            _ = await self._notifications.notify_admins(
                NotificationKind.APPEAL_FILED,
                payload,
                f"appeal:{filed.appeal_id}",
            )
            await self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.STUDENT,
                    actor_id=str(work.student_ref),
                    action="review.appealed",
                    entity="verdict",
                    entity_id=str(verdict.verdict_id),
                    after={"appeal_id": str(filed.appeal_id)},
                ),
            )
            await self._uow.commit()
        return filed

    async def _refuse_unless_open(self, verdict: Verdict | None) -> None:
        if verdict is None:
            reason = "not_published"
            raise AppealNotAllowedError(reason)
        existing = await self._appeals.of_verdict(verdict.verdict_id)
        if existing is not None:
            reason = "already_appealed"
            raise AppealNotAllowedError(reason)
        if verdict.status is VerdictStatus.FINAL:
            reason = "teacher_final"
            raise AppealNotAllowedError(reason)
        if verdict.status is not VerdictStatus.PUBLISHED:
            reason = "not_published"
            raise AppealNotAllowedError(reason)
        published_at = verdict.published_at
        if published_at is None or self._clock.now() > appeal_open_until(published_at):
            reason = "too_late"
            raise AppealNotAllowedError(reason)
