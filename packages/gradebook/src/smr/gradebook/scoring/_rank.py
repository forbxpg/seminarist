"""Places in a group: standard competition ranking."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping
    from decimal import Decimal


def rank(totals: Mapping[uuid.UUID, Decimal]) -> dict[uuid.UUID, int]:
    """Place the students by total, the highest first; equal totals share a place.

    Args:
        totals: Mapping[uuid.UUID, Decimal] - Each student's total.

    Returns:
        dict[uuid.UUID, int] - Each student's place: 1, 2, 2, 4, …

    """
    ordered = sorted(totals.values(), reverse=True)
    first_place: dict[Decimal, int] = {}
    for index, total in enumerate(ordered, start=1):
        _ = first_place.setdefault(total, index)
    return {student: first_place[total] for student, total in totals.items()}
