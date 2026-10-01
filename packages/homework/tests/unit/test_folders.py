"""Folder names that work on every disk."""

from __future__ import annotations

import pytest

from smr.homework.domain import folder_name


@pytest.mark.parametrize(
    ("name", "folder"),
    [
        ("Иванов Иван", "Иванов Иван"),
        ('Пётр "Великий" / II', "Пётр _Великий_ _ II"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("Анна.  ", "Анна"),
        ("...", "_"),
    ],
)
def test_names_become_safe_folders(name: str, folder: str) -> None:
    """Forbidden characters, reserved names and trailing dots are handled."""
    assert folder_name(name) == folder


def test_long_names_are_cut() -> None:
    """A folder name has at most 80 characters."""
    assert len(folder_name("Я" * 300)) == 80
