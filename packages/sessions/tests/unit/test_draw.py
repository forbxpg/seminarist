"""Drawing a student by weight."""

from __future__ import annotations

import random
import uuid
from collections import Counter

import pytest

from smr.sessions.domain import draw


def test_draw_follows_the_weights() -> None:
    """Over many draws, a three times heavier student comes up about three times as often."""
    heavy, light = uuid.uuid4(), uuid.uuid4()
    rng = random.Random(7)  # ruff: ignore[suspicious-non-cryptographic-random-usage] -- a seeded generator to test the shape
    counts = Counter(draw({heavy: 0.75, light: 0.25}, rng) for _ in range(4000))
    assert counts[heavy] / counts[light] == pytest.approx(3, rel=0.15)


def test_draw_of_nobody_is_an_error() -> None:
    """There is nothing to draw from an empty set."""
    with pytest.raises(ValueError, match="nobody"):
        draw({})
