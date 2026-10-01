"""Clock: the current moment, replaceable in tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, final
from zoneinfo import ZoneInfo

# Every deadline, session date and "today" a person sees is told in Moscow time.
MOSCOW = ZoneInfo("Europe/Moscow")


class Clock(Protocol):
    """Tells the current moment."""

    def now(self) -> datetime:
        """Tell the moment.

        Returns:
            datetime - Now, timezone-aware.

        """
        ...


@final
class SystemClock:
    """The machine's clock, in UTC."""

    def now(self) -> datetime:  # ruff: ignore[no-self-use] -- the protocol is an instance method
        """Tell the moment.

        Returns:
            datetime - Now, in UTC.

        """
        return datetime.now(UTC)


@final
class FixedClock:
    """A clock that stands still until moved; for tests and replays."""

    def __init__(self, moment: datetime) -> None:
        self._moment: datetime = moment

    def now(self) -> datetime:
        """Tell the moment.

        Returns:
            datetime - The moment it stands at.

        """
        return self._moment

    def advance(self, delta: timedelta) -> None:
        """Move the clock.

        Args:
            delta: timedelta - How far.

        """
        self._moment += delta
