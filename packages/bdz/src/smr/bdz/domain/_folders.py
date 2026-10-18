"""Folder names for exports: readable, and safe on Windows."""

from __future__ import annotations

import re
import unicodedata

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)},
)
_MAX_LENGTH = 80


def folder_name(name: str) -> str:
    """Turn a person's name into a folder name that works on Windows and macOS.

    Args:
        name: str - A name as typed.

    Returns:
        str - Letters kept, forbidden characters replaced with `_`, no trailing dots
        or spaces, never a reserved device name, at most 80 characters.

    """
    clean = _FORBIDDEN.sub("_", unicodedata.normalize("NFC", name)).strip(" .")
    clean = clean[:_MAX_LENGTH].strip(" .") or "_"
    if clean.split(".")[0].upper() in _RESERVED:
        clean = f"_{clean}"
    return clean
