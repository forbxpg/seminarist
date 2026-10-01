"""Names as the teacher pastes them."""

from __future__ import annotations

MAX_NAME_LENGTH = 200


def normalize_name(raw: str) -> str:
    """Tidy a name: trim it and collapse inner whitespace.

    Args:
        raw: str - A name as typed.

    Returns:
        str - The tidy name; empty when there was nothing but whitespace.

    """
    return " ".join(raw.split())


def parse_roster(text: str) -> list[str]:
    """Read a pasted roster: one name per line, numbering and bullets ignored.

    Args:
        text: str - What the teacher pasted.

    Returns:
        list[str] - Distinct tidy names in their order, none longer than the limit.

    Raises:
        ValueError: If a name is longer than the limit.

    """
    names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        name = normalize_name(_strip_marker(line))
        if not name or name in seen:
            continue
        if len(name) > MAX_NAME_LENGTH:
            msg = f"a name is longer than {MAX_NAME_LENGTH} characters"
            raise ValueError(msg)
        seen.add(name)
        names.append(name)
    return names


def _strip_marker(line: str) -> str:
    """Drop a leading "1.", "1)", "-" or "•" of a pasted list.

    Args:
        line: str - A line as pasted.

    Returns:
        str - The line without its marker.

    """
    stripped = line.strip()
    head, _, rest = stripped.partition(" ")
    if head in {"-", "•", "*"} or (head[:-1].isdigit() and head[-1:] in {".", ")"}):
        return rest
    return stripped
