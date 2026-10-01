"""The board priority: who should be called more often."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Collection, Mapping


def priority_weights(
    population: Mapping[uuid.UUID, tuple[int, float]],
    candidates: Collection[uuid.UUID],
    *,
    board_weight: float,
    score_weight: float,
) -> dict[uuid.UUID, float]:
    """Weigh the candidates: fewer board calls and a lower score weigh more.

    Each student's board calls and score are turned into mid-rank percentiles within
    the whole group, so the weights adapt to the group: an indicator on which everyone
    is equal places everyone at 0.5 and changes no one's chance.

    Args:
        population: Mapping[uuid.UUID, tuple[int, float]] - Every student of the group:
            board calls this semester and the share of the in-priority caps earned.
        candidates: Collection[uuid.UUID] - Those who may be called now.
        board_weight: float - How much past calls lower the chance.
        score_weight: float - How much a high score lowers the chance.

    Returns:
        dict[uuid.UUID, float] - Each candidate's probability; they sum to 1.

    """
    if not candidates:
        return {}
    calls = {student: float(data[0]) for student, data in population.items()}
    scores = {student: data[1] for student, data in population.items()}
    board_rank = _mid_rank(calls)
    score_rank = _mid_rank(scores)
    raw = {
        student: 1.0
        / (
            1.0
            + board_weight * board_rank.get(student, 0.5)
            + score_weight * score_rank.get(student, 0.5)
        )
        for student in candidates
    }
    total = sum(raw.values())
    return {student: weight / total for student, weight in raw.items()}


def _mid_rank(values: Mapping[uuid.UUID, float]) -> dict[uuid.UUID, float]:
    population = list(values.values())
    size = len(population)
    result: dict[uuid.UUID, float] = {}
    for student, value in values.items():
        below = sum(1 for other in population if other < value)
        equal = sum(1 for other in population if other == value)
        result[student] = (below + 0.5 * equal) / size
    return result
