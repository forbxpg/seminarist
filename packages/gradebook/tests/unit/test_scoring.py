"""The arithmetic of the ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from smr.gradebook.domain import (
    GradeEntry,
    GradeItem,
    ScoringMode,
    WorkType,
    WorkTypeKind,
)
from smr.gradebook.scoring import (
    distribution,
    priority_weights,
    rank,
    score_student,
)

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)
GROUP = uuid.uuid4()
ALICE = uuid.uuid4()


def _type(
    mode: ScoringMode,
    cap: int,
    *,
    in_priority: bool = True,
    kind: WorkTypeKind = WorkTypeKind.OTHER,
) -> WorkType:
    return WorkType(
        work_type_id=uuid.uuid4(),
        group_id=GROUP,
        title="t",
        kind=kind,
        mode=mode,
        cap=Decimal(cap),
        in_priority=in_priority,
        position=0,
    )


def _item(
    work_type: WorkType,
    max_points: int,
    counts_from: datetime = NOW,
) -> GradeItem:
    return GradeItem(
        uuid.uuid4(),
        work_type.work_type_id,
        "i",
        Decimal(max_points),
        counts_from,
    )


def _entry(
    work_type: WorkType,
    points: str,
    item: GradeItem | None = None,
    *,
    excused: bool = False,
    student: uuid.UUID = ALICE,
) -> GradeEntry:
    return GradeEntry(
        entry_id=uuid.uuid4(),
        student_id=student,
        work_type_id=work_type.work_type_id,
        item_id=None if item is None else item.item_id,
        points=Decimal(points),
        excused=excused,
        comment=None,
        graded_by=None,
        graded_at=NOW,
    )


def test_proportional_is_a_share_of_what_was_issued() -> None:
    """Three homeworks of 3 points, 7 earned: 12 × 7/9."""
    homework = _type(ScoringMode.PROPORTIONAL, 12)
    items = [_item(homework, 3) for _ in range(3)]
    entries = [
        _entry(homework, p, i) for p, i in zip(("3", "2", "2"), items, strict=True)
    ]
    part = score_student(ALICE, [homework], items, entries, NOW).parts[0]
    assert part.score == Decimal("9.33")
    assert (part.earned, part.possible) == (Decimal(7), Decimal(9))


def test_a_missed_item_counts_as_zero_once_due() -> None:
    """An item past its start counts against a student who has nothing for it."""
    homework = _type(ScoringMode.PROPORTIONAL, 10)
    done, missed = _item(homework, 5), _item(homework, 5)
    entries = [_entry(homework, "5", done)]
    assert score_student(
        ALICE,
        [homework],
        [done, missed],
        entries,
        NOW,
    ).total == Decimal(5)


def test_an_item_not_yet_due_does_not_count() -> None:
    """A homework before its deadline is not held against anyone."""
    homework = _type(ScoringMode.PROPORTIONAL, 10)
    done = _item(homework, 5)
    upcoming = _item(homework, 5, NOW + timedelta(days=3))
    entries = [_entry(homework, "4", done)]
    assert score_student(
        ALICE,
        [homework],
        [done, upcoming],
        entries,
        NOW,
    ).total == Decimal(8)


def test_an_item_graded_early_counts_for_that_student() -> None:
    """A homework graded before its deadline already counts for its author."""
    homework = _type(ScoringMode.PROPORTIONAL, 10)
    upcoming = _item(homework, 5, NOW + timedelta(days=3))
    entries = [_entry(homework, "5", upcoming)]
    assert score_student(ALICE, [homework], [upcoming], entries, NOW).total == Decimal(
        10,
    )


def test_an_excused_item_leaves_the_denominator() -> None:
    """Excused from one of two sessions, present at the other: full score."""
    attendance = _type(ScoringMode.PROPORTIONAL, 4)
    first, second = _item(attendance, 1), _item(attendance, 1)
    entries = [
        _entry(attendance, "1", first),
        _entry(attendance, "0", second, excused=True),
    ]
    assert score_student(
        ALICE,
        [attendance],
        [first, second],
        entries,
        NOW,
    ).total == Decimal(4)


def test_nothing_issued_scores_zero_and_says_so() -> None:
    """A work type with nothing issued yet is not counted."""
    tests = _type(ScoringMode.PROPORTIONAL, 24)
    part = score_student(ALICE, [tests], [], [], NOW).parts[0]
    assert (part.score, part.counted) == (Decimal(0), False)


def test_accumulating_stops_at_the_cap() -> None:
    """Board points sum up to the cap and no further."""
    board = _type(ScoringMode.ACCUMULATING, 8)
    entries = [_entry(board, "3") for _ in range(4)]
    assert score_student(ALICE, [board], [], entries, NOW).total == Decimal(8)


def test_other_students_entries_are_ignored() -> None:
    """Only the student's own entries count."""
    board = _type(ScoringMode.ACCUMULATING, 8)
    entries = [_entry(board, "3", student=uuid.uuid4())]
    assert score_student(ALICE, [board], [], entries, NOW).total == Decimal(0)


def test_rank_shares_places_on_ties() -> None:
    """Totals 40, 30, 30, 10 give places 1, 2, 2, 4."""
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    places = rank({a: Decimal(40), b: Decimal(30), c: Decimal(30), d: Decimal(10)})
    assert [places[s] for s in (a, b, c, d)] == [1, 2, 2, 4]


def test_distribution_hides_bands_of_one_or_two() -> None:
    """A band with two students says only that there are fewer than three."""
    totals = [
        Decimal(5),
        Decimal(45),
        Decimal(46),
        Decimal(47),
        Decimal(30),
        Decimal(31),
    ]
    bands = distribution(totals, Decimal(50))
    assert [(b.low_percent, b.count) for b in bands] == [
        (0, None),
        (20, 0),
        (40, 0),
        (60, None),
        (80, 3),
    ]


def test_distribution_puts_the_full_score_in_the_top_band() -> None:
    """A total equal to the caps' sum is in the last band."""
    bands = distribution([Decimal(50)] * 3, Decimal(50))
    assert bands[-1].count == 3


def test_priority_is_uniform_when_everyone_is_equal() -> None:
    """Equal calls and scores give equal chances."""
    students = [uuid.uuid4() for _ in range(4)]
    population = dict.fromkeys(students, (2, 0.5))
    weights = priority_weights(population, students, board_weight=1, score_weight=1)
    assert all(w == pytest.approx(0.25) for w in weights.values())


def test_priority_favours_the_rarely_called_and_the_weaker() -> None:
    """Fewer calls and a lower score give a higher chance."""
    rare_weak, rare_strong, often_strong = (uuid.uuid4() for _ in range(3))
    population = {rare_weak: (0, 0.2), rare_strong: (0, 0.9), often_strong: (5, 0.9)}
    weights = priority_weights(
        population,
        list(population),
        board_weight=1,
        score_weight=1,
    )
    assert weights[rare_weak] > weights[rare_strong] > weights[often_strong]
    assert sum(weights.values()) == pytest.approx(1)


def test_priority_ignores_an_indicator_everyone_shares() -> None:
    """When everyone has the same score, only the calls decide."""
    a, b = uuid.uuid4(), uuid.uuid4()
    population = {a: (0, 0.5), b: (3, 0.5)}
    with_score = priority_weights(population, [a, b], board_weight=1, score_weight=5)
    without_score = priority_weights(population, [a, b], board_weight=1, score_weight=0)
    assert with_score[a] > with_score[b]
    assert without_score[a] > without_score[b]


def test_priority_of_no_candidates_is_empty() -> None:
    """Nobody to call, no weights."""
    assert priority_weights({}, [], board_weight=1, score_weight=1) == {}
