"""What the teacher and the students do with groups and rosters."""

from __future__ import annotations

from ._binding import (
    AcceptConsent,
    ApproveBinding,
    ClaimableNames,
    ClaimStudent,
    ForgetAccount,
    Memberships,
    PendingBindings,
    RejectBinding,
    ResolveInvite,
    Unbind,
)
from ._groups import (
    ArchiveGroup,
    CreateGroup,
    GroupsDueForPurge,
    ListGroups,
    PurgeGroup,
    RotateInvite,
    UpdateGroupSettings,
)
from ._results import ImportResult, Membership
from ._roster import (
    ImportRoster,
    ListStudents,
    RemoveStudent,
    RenameStudent,
    SetJournalNumber,
)

__all__ = (
    "AcceptConsent",
    "ApproveBinding",
    "ArchiveGroup",
    "ClaimStudent",
    "ClaimableNames",
    "CreateGroup",
    "ForgetAccount",
    "GroupsDueForPurge",
    "ImportResult",
    "ImportRoster",
    "ListGroups",
    "ListStudents",
    "Membership",
    "Memberships",
    "PendingBindings",
    "PurgeGroup",
    "RejectBinding",
    "RemoveStudent",
    "RenameStudent",
    "ResolveInvite",
    "RotateInvite",
    "SetJournalNumber",
    "Unbind",
    "UpdateGroupSettings",
)
