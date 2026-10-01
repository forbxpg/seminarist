"""The clocks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from smr.core.clock import FixedClock, SystemClock


def test_system_clock_is_aware() -> None:
    """The system clock tells UTC."""
    assert SystemClock().now().tzinfo is UTC


def test_fixed_clock_moves_only_when_told() -> None:
    """A fixed clock stands until advanced."""
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(timedelta(hours=1))
    assert clock.now() == datetime(2026, 1, 1, 1, tzinfo=UTC)
