"""Parsing a point scheme."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smr.bdz.domain import InvalidSchemeError, parse_scheme


def test_scheme_parses() -> None:
    """Commas, spaces, newlines and both separators are one scheme."""
    tasks = parse_scheme("1:3, 2:2.5\n3=1")
    assert [task.number for task in tasks] == [1, 2, 3]
    assert sum(task.max_points for task in tasks) == Decimal("6.5")


@pytest.mark.parametrize(
    "text",
    ["1:3 3:2", "1:0", "1:3, 1:2", "1:3.333", " ".join(f"{n}:1" for n in range(1, 52))],
)
def test_scheme_refuses(text: str) -> None:
    """A gap, a zero, a duplicate, a third decimal or 51 tasks is refused."""
    with pytest.raises(InvalidSchemeError):
        parse_scheme(text)
