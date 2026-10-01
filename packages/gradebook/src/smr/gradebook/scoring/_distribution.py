"""How a group's totals spread, coarse enough to name no one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from decimal import Decimal

BUCKET_PERCENT = 20
"""Width of a bucket, in percent of the caps' sum."""

MIN_SHOWN = 3
"""A bucket holding fewer students than this hides its count."""


@dataclass(frozen=True, slots=True)
class Bucket:
    """A band of totals.

    Attributes:
        low_percent: int - Lower bound, in percent of the caps' sum, inclusive.
        high_percent: int - Upper bound, exclusive; the last band includes 100.
        count: int | None - Students in it; none when 1 or 2, to name no one.

    """

    low_percent: int
    high_percent: int
    count: int | None


def distribution(totals: Iterable[Decimal], cap_total: Decimal) -> tuple[Bucket, ...]:
    """Spread the totals over five bands.

    Args:
        totals: Iterable[Decimal] - Every student's total.
        cap_total: Decimal - The caps' sum.

    Returns:
        tuple[Bucket, ...] - The bands from the lowest.

    """
    counts = [0] * (100 // BUCKET_PERCENT)
    if cap_total > 0:
        for total in totals:
            percent = total * 100 / cap_total
            index = min(int(percent // BUCKET_PERCENT), len(counts) - 1)
            counts[max(index, 0)] += 1
    return tuple(
        Bucket(
            low_percent=index * BUCKET_PERCENT,
            high_percent=(index + 1) * BUCKET_PERCENT,
            count=None if 0 < count < MIN_SHOWN else count,
        )
        for index, count in enumerate(counts)
    )
