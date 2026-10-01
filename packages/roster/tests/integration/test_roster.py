"""Groups, rosters and binding over a real database."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER

from smr.core.access import NotAdminError
from smr.roster.domain import (
    AlreadyBoundError,
    BindingStatus,
    GroupArchivedError,
    GroupSettings,
    InviteNotFoundError,
    NameTakenError,
    NotPendingError,
    StudentNotFoundError,
)

if TYPE_CHECKING:
    from roster_kit import Roster

    from smr.roster.domain import Group

pytestmark = pytest.mark.integration


async def _group(roster: Roster, names: str = "Иванов Иван\nПетров Пётр") -> Group:
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, names)
    return group


async def test_only_a_teacher_creates_a_group(roster: Roster) -> None:
    """A student's account is refused by the use case itself."""
    with pytest.raises(NotAdminError):
        await roster.create(STUDENT, title="x", subject="y", semester="z")


async def test_import_skips_names_already_there(roster: Roster) -> None:
    """A second paste adds only the new names."""
    group = await _group(roster)
    result = await roster.import_(TEACHER, group.group_id, "Петров Пётр\nСидорова Анна")
    assert (result.added, result.skipped) == (1, 1)
    assert [s.full_name for s in await roster.api.students_of(group.group_id)] == [
        "Иванов Иван",
        "Петров Пётр",
        "Сидорова Анна",
    ]


async def test_claim_waits_for_the_teacher(roster: Roster) -> None:
    """A claimed name is pending, gone from the free names, bound once approved."""
    group = await _group(roster)
    free = await roster.claimable(group.invite_code)
    chosen = free[0]
    membership = await roster.claim(group.invite_code, chosen.student_id, STUDENT, "v1")
    assert membership.student.binding is BindingStatus.PENDING
    assert chosen.student_id not in {
        s.student_id for s in await roster.claimable(group.invite_code)
    }
    assert await roster.api.bound_student(STUDENT, group.group_id) is None
    assert [m.student.student_id for m in await roster.pending(TEACHER)] == [
        chosen.student_id,
    ]

    bound = await roster.approve(TEACHER, chosen.student_id)
    assert bound.binding is BindingStatus.BOUND
    found = await roster.api.bound_student(STUDENT, group.group_id)
    assert found is not None
    assert found.consent_version == "v1"


async def test_a_name_is_claimed_once(roster: Roster) -> None:
    """Another account cannot take a name someone already claimed."""
    group = await _group(roster)
    chosen = (await roster.claimable(group.invite_code))[0]
    _ = await roster.claim(group.invite_code, chosen.student_id, STUDENT, "v1")
    with pytest.raises(NameTakenError):
        await roster.claim(group.invite_code, chosen.student_id, STUDENT + 1, "v1")


async def test_one_account_holds_one_row_per_group(roster: Roster) -> None:
    """An account that claimed a name cannot claim a second one."""
    group = await _group(roster)
    first, second = await roster.claimable(group.invite_code)
    _ = await roster.claim(group.invite_code, first.student_id, STUDENT, "v1")
    with pytest.raises(AlreadyBoundError):
        await roster.claim(group.invite_code, second.student_id, STUDENT, "v1")


async def test_a_row_of_another_group_cannot_be_claimed(roster: Roster) -> None:
    """The chosen row must belong to the link's group."""
    first = await _group(roster)
    other = await roster.create(
        TEACHER,
        title="К01-262",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, other.group_id, "Кузнецов Кирилл")
    stranger = (await roster.api.students_of(other.group_id))[0]
    with pytest.raises(StudentNotFoundError):
        await roster.claim(first.invite_code, stranger.student_id, STUDENT, "v1")


async def test_reject_frees_the_name(roster: Roster) -> None:
    """A rejected claim leaves no account and no consent behind."""
    group = await _group(roster)
    chosen = (await roster.claimable(group.invite_code))[0]
    _ = await roster.claim(group.invite_code, chosen.student_id, STUDENT, "v1")
    rejected = await roster.reject(TEACHER, chosen.student_id)
    assert rejected.tg_user_id == STUDENT
    again = await roster.api.student(chosen.student_id)
    assert again is not None
    assert (again.binding, again.tg_user_id, again.consent_version) == (
        BindingStatus.UNBOUND,
        None,
        None,
    )
    with pytest.raises(NotPendingError):
        await roster.approve(TEACHER, chosen.student_id)


async def test_rotated_invite_stops_the_old_link(roster: Roster) -> None:
    """The old code is unknown after rotation."""
    group = await _group(roster)
    code = await roster.rotate(TEACHER, group.group_id)
    assert code != group.invite_code
    with pytest.raises(InviteNotFoundError):
        await roster.claimable(group.invite_code)
    assert len(await roster.claimable(code)) == 2


async def test_archived_group_takes_no_one(roster: Roster) -> None:
    """An archived group neither takes claims nor shows in memberships."""
    group = await _group(roster)
    chosen = (await roster.claimable(group.invite_code))[0]
    _ = await roster.claim(group.invite_code, chosen.student_id, STUDENT, "v1")
    await roster.archive(TEACHER, group.group_id)
    with pytest.raises(GroupArchivedError):
        await roster.claimable(group.invite_code)
    assert await roster.memberships(STUDENT) == []


async def test_purge_after_retention(roster: Roster) -> None:
    """An archived group is due for purge only after its retention."""
    group = await _group(roster)
    _ = await roster.settings(TEACHER, group.group_id, GroupSettings(retention_days=30))
    await roster.archive(TEACHER, group.group_id)
    roster.clock.advance(timedelta(days=29))
    assert await roster.due() == []
    roster.clock.advance(timedelta(days=2))
    assert [g.group_id for g in await roster.due()] == [group.group_id]
    await roster.purge(group.group_id)
    assert await roster.api.group(group.group_id) is None
    assert await roster.api.students_of(group.group_id) == []


async def test_forget_unbinds_every_row(roster: Roster) -> None:
    """Forgetting an account leaves no binding of it anywhere."""
    group = await _group(roster)
    chosen = (await roster.claimable(group.invite_code))[0]
    _ = await roster.claim(group.invite_code, chosen.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, chosen.student_id)
    forgotten = await roster.forget(STUDENT)
    assert [s.student_id for s in forgotten] == [chosen.student_id]
    assert await roster.memberships(STUDENT) == []


async def test_settings_are_checked(roster: Roster) -> None:
    """A reminder two weeks before the deadline is out of range."""
    group = await _group(roster)
    with pytest.raises(ValueError, match="reminder"):
        await roster.settings(
            TEACHER,
            group.group_id,
            GroupSettings(reminder_hours=24 * 14),
        )
