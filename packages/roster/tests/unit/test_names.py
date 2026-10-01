"""Reading a pasted roster."""

from __future__ import annotations

import pytest

from smr.roster.domain import MAX_NAME_LENGTH, new_invite_code, parse_roster


def test_reads_one_name_per_line() -> None:
    """Numbering, bullets, blank lines and repeats are dropped; spaces are tidied."""
    text = "1. Иванов  Иван\n2) Петров Пётр\n\n- Сидорова Анна\n• Иванов Иван\n   \n"
    assert parse_roster(text) == ["Иванов Иван", "Петров Пётр", "Сидорова Анна"]


def test_keeps_a_name_that_starts_with_a_number_word() -> None:
    """A line without a list marker is taken as it is."""
    assert parse_roster("Ли Ён") == ["Ли Ён"]


def test_refuses_a_name_too_long() -> None:
    """A line longer than the limit is an error, not silently cut."""
    with pytest.raises(ValueError, match="longer"):
        parse_roster("Я" * (MAX_NAME_LENGTH + 1))


def test_invite_codes_fit_a_deep_link() -> None:
    """Codes are distinct and made of deep-link characters only."""
    codes = {new_invite_code() for _ in range(100)}
    assert len(codes) == 100
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
    assert all(len(code) <= 64 and set(code) <= allowed for code in codes)
