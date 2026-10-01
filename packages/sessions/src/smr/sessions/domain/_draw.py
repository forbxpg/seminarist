"""Drawing a student by weight."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping

_SYSTEM_RANDOM = random.SystemRandom()


def draw(
    weights: Mapping[uuid.UUID, float],
    rng: random.Random = _SYSTEM_RANDOM,
) -> uuid.UUID:
    """Pick one candidate with probability proportional to its weight.

    Args:
        weights: Mapping[uuid.UUID, float] - Each candidate's weight; not empty.
        rng: random.Random - Source of randomness; the OS's by default.

    Returns:
        uuid.UUID - The drawn candidate.

    Raises:
        ValueError: If there are no candidates.

    """
    if not weights:
        msg = "nobody to draw"
        raise ValueError(msg)
    candidates = list(weights)
    return rng.choices(candidates, weights=[weights[c] for c in candidates], k=1)[0]
