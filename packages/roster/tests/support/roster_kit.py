"""The roster's use cases over one session, for the integration tests of every package."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest

from smr.core.access import AdminGuard
from smr.core.audit import SqlAlchemyAuditLog
from smr.core.clock import FixedClock
from smr.core.database import SqlAlchemyUnitOfWork
from smr.roster.application.use_cases import (
    AcceptConsent,
    ApproveBinding,
    ArchiveGroup,
    ClaimableNames,
    ClaimStudent,
    CreateGroup,
    ForgetAccount,
    GroupsDueForPurge,
    ImportRoster,
    Memberships,
    PendingBindings,
    PurgeGroup,
    RejectBinding,
    RemoveStudent,
    RotateInvite,
    SetJournalNumber,
    Unbind,
    UpdateGroupSettings,
)
from smr.roster.infrastructure.repositories import (
    SqlAlchemyGroups,
    SqlAlchemyRosterApi,
    SqlAlchemyStudents,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ("STUDENT", "TEACHER", "Roster", "roster")

TEACHER = 1
STUDENT = 500


@final
class Roster:
    """The roster's use cases bound to one session, the way the bot builds them."""

    def __init__(self, session: AsyncSession) -> None:
        groups = SqlAlchemyGroups(session)
        students = SqlAlchemyStudents(session)
        uow = SqlAlchemyUnitOfWork(session)
        audit = SqlAlchemyAuditLog(session)
        guard = AdminGuard({TEACHER})
        self.clock = FixedClock(datetime(2026, 10, 2, 9, tzinfo=UTC))
        self.api = SqlAlchemyRosterApi(session)
        self.create = CreateGroup(groups, uow, audit, guard)
        self.settings = UpdateGroupSettings(groups, uow, audit, guard)
        self.rotate = RotateInvite(groups, uow, audit, guard)
        self.archive = ArchiveGroup(groups, uow, audit, guard, self.clock)
        self.due = GroupsDueForPurge(groups, self.clock)
        self.purge = PurgeGroup(groups, uow, audit)
        self.import_ = ImportRoster(groups, students, uow, audit, guard)
        self.journal = SetJournalNumber(students, uow, audit, guard)
        self.claimable = ClaimableNames(groups, students)
        self.claim = ClaimStudent(groups, students, uow, audit, self.clock)
        self.pending = PendingBindings(groups, students, guard)
        self.approve = ApproveBinding(students, uow, audit, guard)
        self.accept = AcceptConsent(students, uow, audit, self.clock)
        self.reject = RejectBinding(students, uow, audit, guard)
        self.unbind = Unbind(students, uow, audit, guard)
        self.memberships = Memberships(groups, students)
        self.forget = ForgetAccount(students, uow, audit)
        self.remove = RemoveStudent(students, uow, audit, guard)


@pytest.fixture
def roster(session: AsyncSession) -> Roster:
    """Give the roster's use cases over the test's session."""
    return Roster(session)
