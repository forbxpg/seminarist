"""The point scheme a teacher types."""

from __future__ import annotations

import re
from decimal import Decimal

from smr.review.domain import SchemeTask

from ._errors import InvalidSchemeError

_SPLIT = re.compile(r"[\s,]+")
_PART = re.compile(r"^(\d+)\s*[:=]\s*(\d+(?:\.\d+)?)$")
_CENT = Decimal("0.01")
_MAX_TASKS = 50


def parse_scheme(text: str) -> tuple[SchemeTask, ...]:
    """Read `1:3, 2:2.5` into tasks numbered from 1.

    Args:
        text: str - Tasks separated by commas, spaces or newlines. `:` or `=`.

    Returns:
        tuple[SchemeTask, ...] - The tasks, in order.

    Raises:
        InvalidSchemeError: If the tasks are gapped, duplicated, empty, over 50,
            or a maximum is not a positive amount of cents.

    """
    chunks = [chunk for chunk in _SPLIT.split(text.strip()) if chunk]
    if not chunks or len(chunks) > _MAX_TASKS:
        raise InvalidSchemeError
    tasks: list[SchemeTask] = []
    for chunk in chunks:
        match = _PART.fullmatch(chunk)
        if match is None:
            raise InvalidSchemeError
        points = Decimal(match.group(2))
        if points <= 0 or points != points.quantize(_CENT):
            raise InvalidSchemeError
        tasks.append(SchemeTask(int(match.group(1)), points))
    numbers = [task.number for task in tasks]
    if numbers != list(range(1, len(numbers) + 1)):
        raise InvalidSchemeError
    return tuple(tasks)
