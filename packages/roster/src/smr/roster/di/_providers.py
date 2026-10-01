"""The roster's repositories, contract and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.roster.application.contracts import RosterApi
from smr.roster.application.ports import GroupRepository, StudentRepository
from smr.roster.application.use_cases import (
    ApproveBinding,
    ArchiveGroup,
    ClaimableNames,
    ClaimStudent,
    CreateGroup,
    ForgetAccount,
    GroupsDueForPurge,
    ImportRoster,
    ListGroups,
    ListStudents,
    Memberships,
    PendingBindings,
    PurgeGroup,
    RejectBinding,
    RemoveStudent,
    RenameStudent,
    ResolveInvite,
    RotateInvite,
    Unbind,
    UpdateGroupSettings,
)
from smr.roster.infrastructure.repositories import (
    SqlAlchemyGroups,
    SqlAlchemyRosterApi,
    SqlAlchemyStudents,
)


@final
class RosterProvider(Provider):
    """Everything of the roster, built per update or task."""

    scope = Scope.REQUEST

    groups = provide(SqlAlchemyGroups, provides=GroupRepository)
    students = provide(SqlAlchemyStudents, provides=StudentRepository)
    api = provide(SqlAlchemyRosterApi, provides=RosterApi)

    use_cases = provide_all(
        ApproveBinding,
        ArchiveGroup,
        ClaimStudent,
        ClaimableNames,
        CreateGroup,
        ForgetAccount,
        GroupsDueForPurge,
        ImportRoster,
        ListGroups,
        ListStudents,
        Memberships,
        PendingBindings,
        PurgeGroup,
        RejectBinding,
        RemoveStudent,
        RenameStudent,
        ResolveInvite,
        RotateInvite,
        Unbind,
        UpdateGroupSettings,
    )
