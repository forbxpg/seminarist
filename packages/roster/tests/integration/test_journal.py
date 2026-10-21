"""Numbers in the group's journal: set, cleared, unique within a group."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from roster_kit import TEACHER

from smr.roster.domain import JournalNumberTakenError

if TYPE_CHECKING:
    from roster_kit import Roster

    from smr.roster.domain import Student

pytestmark = pytest.mark.integration


async def _two(roster: Roster) -> list[Student]:
    group = await roster.create(
        TEACHER,
        title="Б26-514",
        subject="ДМ",
        semester="осень",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов\nПетров")
    return sorted(
        await roster.api.students_of(group.group_id),
        key=lambda s: s.full_name,
    )


async def test_number_is_set_and_cleared(roster: Roster) -> None:
    """The teacher sets a number and can clear it."""
    ivanov, _ = await _two(roster)
    await roster.journal(TEACHER, ivanov.student_id, 11)
    found = await roster.api.student(ivanov.student_id)
    assert found is not None
    assert found.journal_no == 11
    await roster.journal(TEACHER, ivanov.student_id, None)
    cleared = await roster.api.student(ivanov.student_id)
    assert cleared is not None
    assert cleared.journal_no is None


async def test_number_is_unique_in_a_group(roster: Roster) -> None:
    """Two students of one group cannot share a number."""
    ivanov, petrov = await _two(roster)
    await roster.journal(TEACHER, ivanov.student_id, 3)
    with pytest.raises(JournalNumberTakenError):
        await roster.journal(TEACHER, petrov.student_id, 3)


@pytest.mark.parametrize("number", [0, 1000])
async def test_number_out_of_range_is_refused(roster: Roster, number: int) -> None:
    """A journal number is 1..999."""
    ivanov, _ = await _two(roster)
    with pytest.raises(ValueError, match="1 to 999"):
        await roster.journal(TEACHER, ivanov.student_id, number)
