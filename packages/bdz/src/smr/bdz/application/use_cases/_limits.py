"""How long a БДЗ PDF may be."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BdzLimits:
    """The page cap for a БДЗ PDF.

    Attributes:
        max_pages: int - The most pages accepted.

    """

    max_pages: int
