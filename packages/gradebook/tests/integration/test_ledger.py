"""The ledger over a real database."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER

from smr.gradebook.application.use_cases import EXCUSED
from smr.gradebook.domain import (
    EntryNotFoundError,
    PointsOutOfRangeError,
    ScoringMode,
    WorkTypeInUseError,
    WorkTypeKind,
    WorkTypeKindTakenError,
)
from smr.roster.domain import StudentNotFoundError

if TYPE_CHECKING:
    import uuid

    from gradebook_kit import Gradebook

    from smr.gradebook.domain import WorkType
    from smr.roster.domain import Group, Student

pytestmark = pytest.mark.integration


async def _setup(
    gradebook: Gradebook,
) -> tuple[Group, list[Student], dict[WorkTypeKind, WorkType]]:
    roster = gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов\nПетров\nСидоров")
    students = list(await roster.api.students_of(group.group_id))
    types = {t.kind: t for t in await gradebook.scheme(TEACHER, group.group_id)}
    return group, students, types


async def _bind(gradebook: Gradebook, group: Group, student_id: uuid.UUID) -> None:
    roster = gradebook.roster
    _ = await roster.claim(group.invite_code, student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, student_id)


async def test_default_scheme_is_fifty_points(gradebook: Gradebook) -> None:
    """The default scheme's caps sum to 50."""
    _, _, types = await _setup(gradebook)
    assert sum(t.cap for t in types.values()) == Decimal(50)


async def test_a_test_scored_for_the_roster(gradebook: Gradebook) -> None:
    """A test graded for everyone moves the totals and the places."""
    group, (ivanov, petrov, sidorov), types = await _setup(gradebook)
    test = await gradebook.create_item(
        TEACHER,
        types[WorkTypeKind.TEST].work_type_id,
        title="Контрольная 1",
        max_points=Decimal(8),
    )
    await gradebook.set_grades(
        TEACHER,
        test.item_id,
        {
            ivanov.student_id: Decimal(8),
            petrov.student_id: Decimal(4),
            sidorov.student_id: EXCUSED,
        },
    )
    rows = {
        row.student.full_name: row
        for row in await gradebook.sheet(TEACHER, group.group_id)
    }
    assert rows["Иванов"].score.total == Decimal(24)
    assert rows["Петров"].score.total == Decimal(12)
    assert rows["Сидоров"].score.total == Decimal(0)
    assert [rows[n].place for n in ("Иванов", "Петров", "Сидоров")] == [1, 2, 3]
    grades = {
        s.full_name: e
        for s, e in await gradebook.item_grades(TEACHER, test.item_id, group.group_id)
    }
    assert grades["Сидоров"] is not None
    assert grades["Сидоров"].excused


async def test_points_beyond_the_maximum_are_refused(gradebook: Gradebook) -> None:
    """Nine points for an eight-point test stores nothing."""
    _, (ivanov, petrov, _), types = await _setup(gradebook)
    test = await gradebook.create_item(
        TEACHER,
        types[WorkTypeKind.TEST].work_type_id,
        title="К1",
        max_points=Decimal(8),
    )
    with pytest.raises(PointsOutOfRangeError):
        await gradebook.set_grades(
            TEACHER,
            test.item_id,
            {ivanov.student_id: Decimal(5), petrov.student_id: Decimal(9)},
        )


async def test_accumulating_points_and_correction(gradebook: Gradebook) -> None:
    """The teacher's mark is added, then corrected; the cap holds."""
    group, (ivanov, _, _), types = await _setup(gradebook)
    teacher_type = types[WorkTypeKind.TEACHER]
    entry = await gradebook.add_points(
        TEACHER,
        ivanov.student_id,
        teacher_type.work_type_id,
        Decimal(1),
        "активен",
    )
    _ = await gradebook.edit(TEACHER, entry.entry_id, Decimal(2), None)
    with pytest.raises(PointsOutOfRangeError):
        await gradebook.edit(TEACHER, entry.entry_id, Decimal(3), None)
    rows = {
        row.student.full_name: row
        for row in await gradebook.sheet(TEACHER, group.group_id)
    }
    assert rows["Иванов"].score.total == Decimal(2)


async def test_student_sees_only_their_own_report(gradebook: Gradebook) -> None:
    """A bound account reads its report; an unbound one is refused."""
    group, (ivanov, _, _), _ = await _setup(gradebook)
    with pytest.raises(StudentNotFoundError):
        await gradebook.report(STUDENT, group.group_id)
    await _bind(gradebook, group, ivanov.student_id)
    report = await gradebook.report(STUDENT, group.group_id)
    assert report.score.student_id == ivanov.student_id
    assert report.group_size == 3
    assert report.place == 1
    assert report.buckets is not None


async def test_only_one_board_work_type(gradebook: Gradebook) -> None:
    """A second board work type is refused."""
    group, _, _ = await _setup(gradebook)
    with pytest.raises(WorkTypeKindTakenError):
        await gradebook.create_type(
            TEACHER,
            group.group_id,
            title="Ещё доска",
            kind=WorkTypeKind.BOARD,
            mode=ScoringMode.ACCUMULATING,
            cap=Decimal(2),
            in_priority=True,
        )


async def test_a_work_type_with_points_is_kept(gradebook: Gradebook) -> None:
    """A work type someone has points for cannot be deleted."""
    _, (ivanov, _, _), types = await _setup(gradebook)
    teacher_type = types[WorkTypeKind.TEACHER]
    _ = await gradebook.add_points(
        TEACHER,
        ivanov.student_id,
        teacher_type.work_type_id,
        Decimal(1),
        None,
    )
    with pytest.raises(WorkTypeInUseError):
        await gradebook.delete_type(TEACHER, teacher_type.work_type_id)


async def test_cap_change_rescores_everyone(gradebook: Gradebook) -> None:
    """Halving a cap halves the score at once."""
    group, (ivanov, _, _), types = await _setup(gradebook)
    test_type = types[WorkTypeKind.TEST]
    test = await gradebook.create_item(
        TEACHER,
        test_type.work_type_id,
        title="К1",
        max_points=Decimal(8),
    )
    await gradebook.set_grades(TEACHER, test.item_id, {ivanov.student_id: Decimal(8)})
    _ = await gradebook.update_type(
        TEACHER,
        test_type.work_type_id,
        title=test_type.title,
        cap=Decimal(12),
        in_priority=True,
    )
    rows = {
        row.student.full_name: row
        for row in await gradebook.sheet(TEACHER, group.group_id)
    }
    assert rows["Иванов"].score.total == Decimal(12)


async def test_removing_a_student_removes_their_points(gradebook: Gradebook) -> None:
    """A roster row's entries go with it."""
    group, (ivanov, _, _), types = await _setup(gradebook)
    entry = await gradebook.add_points(
        TEACHER,
        ivanov.student_id,
        types[WorkTypeKind.TEACHER].work_type_id,
        Decimal(1),
        None,
    )
    _ = await gradebook.roster.remove(TEACHER, ivanov.student_id)
    assert ivanov.student_id not in await gradebook.ledger.scores(group.group_id)
    with pytest.raises(EntryNotFoundError):
        await gradebook.edit(TEACHER, entry.entry_id, Decimal(1), None)


async def test_priority_weights_cover_the_candidates(gradebook: Gradebook) -> None:
    """Weights are given for the candidates only and sum to one."""
    group, (ivanov, petrov, sidorov), _ = await _setup(gradebook)
    weights = await gradebook.ledger.priority_weights(
        group.group_id,
        {ivanov.student_id: 3},
        [ivanov.student_id, petrov.student_id],
    )
    assert set(weights) == {ivanov.student_id, petrov.student_id}
    assert sidorov.student_id not in weights
    assert weights[petrov.student_id] > weights[ivanov.student_id]
    assert sum(weights.values()) == pytest.approx(1)
