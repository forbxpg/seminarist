"""The scheme a new group may start from: 50 points, tests weigh the most."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ._enums import ScoringMode, WorkTypeKind


@dataclass(frozen=True, slots=True)
class SchemeLine:
    """One work type of a scheme.

    Attributes:
        title: str - Its title.
        kind: WorkTypeKind - What it is for.
        mode: ScoringMode - How it is scored.
        cap: Decimal - Its cap.

    """

    title: str
    kind: WorkTypeKind
    mode: ScoringMode
    cap: Decimal


DEFAULT_SCHEME: tuple[SchemeLine, ...] = (
    SchemeLine("Контрольные", WorkTypeKind.TEST, ScoringMode.PROPORTIONAL, Decimal(24)),
    SchemeLine(
        "Домашние задания",
        WorkTypeKind.HOMEWORK,
        ScoringMode.PROPORTIONAL,
        Decimal(12),
    ),
    SchemeLine(
        "Выходы к доске",
        WorkTypeKind.BOARD,
        ScoringMode.ACCUMULATING,
        Decimal(8),
    ),
    SchemeLine(
        "Посещаемость",
        WorkTypeKind.ATTENDANCE,
        ScoringMode.PROPORTIONAL,
        Decimal(4),
    ),
    SchemeLine(
        "Оценка преподавателя",
        WorkTypeKind.TEACHER,
        ScoringMode.ACCUMULATING,
        Decimal(2),
    ),
)
