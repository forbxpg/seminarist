"""What people type: moments in Moscow time and points."""

from __future__ import annotations

import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from smr.core.clock import MOSCOW

_MOMENT = re.compile(
    r"^\s*(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{2,4}))?"
    r"(?:\s+(?P<hour>\d{1,2})[:.](?P<minute>\d{2}))?\s*$",
)
_END_OF_DAY = time(23, 59)


def parse_moment(text: str, now: datetime) -> datetime:
    """Read "07.10", "07.10 18:30" or "07.10.2026 18:30" as Moscow time.

    A date without a year is the next such date from now; without a time it is the end
    of that day, which is what a deadline usually means.

    Args:
        text: str - What was typed.
        now: datetime - The current moment, aware.

    Returns:
        datetime - The moment, aware, in Moscow time.

    Raises:
        ValueError: If the text is not a date.

    """
    match = _MOMENT.match(text)
    if match is None:
        msg = "type a date like 07.10 or 07.10 18:30"
        raise ValueError(msg)
    day, month = int(match["day"]), int(match["month"])
    hour = int(match["hour"]) if match["hour"] else _END_OF_DAY.hour
    minute = int(match["minute"]) if match["minute"] else _END_OF_DAY.minute
    local_now = now.astimezone(MOSCOW)
    if match["year"]:
        year = int(match["year"])
        year = year + 2000 if year < 100 else year  # ruff: ignore[magic-value-comparison] -- two-digit years
        return datetime(year, month, day, hour, minute, tzinfo=MOSCOW)
    moment = datetime(local_now.year, month, day, hour, minute, tzinfo=MOSCOW)
    if moment < local_now and (local_now - moment).days > 180:  # ruff: ignore[magic-value-comparison] -- half a year
        moment = moment.replace(year=local_now.year + 1)
    return moment


def parse_points(text: str) -> Decimal:
    """Read points: "2", "2.5" or "2,5".

    Args:
        text: str - What was typed.

    Returns:
        Decimal - Not negative, at most two decimals.

    Raises:
        ValueError: If the text is not a number of points.

    """
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation as error:
        msg = "type a number like 2 or 2.5"
        raise ValueError(msg) from error
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        msg = "points are not negative and have at most two decimals"
        raise ValueError(msg)
    return value
