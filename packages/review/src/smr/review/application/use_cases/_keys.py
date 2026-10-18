"""Shared parsing of the keys the agent sends."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from smr.review.application.ports import ReviewSource
from smr.review.domain import UnknownSourceError


def source_of(sources: Sequence[ReviewSource], name: str) -> ReviewSource:
    """Find a source by its name.

    Args:
        sources: Sequence[ReviewSource] - The wired sources.
        name: str - The name.

    Returns:
        ReviewSource - It.

    Raises:
        UnknownSourceError: If none has that name.

    """
    for source in sources:
        if source.name == name:
            return source
    raise UnknownSourceError


def parse_key(key: str) -> tuple[str, uuid.UUID]:
    """Split `source:uuid`.

    Args:
        key: str - A work ref or a task key.

    Returns:
        tuple[str, uuid.UUID] - The source name and the id.

    Raises:
        UnknownSourceError: If the key is not `name:uuid`.

    """
    name, separator, raw = key.partition(":")
    if not separator or not name:
        raise UnknownSourceError
    try:
        return name, uuid.UUID(raw)
    except ValueError as error:
        raise UnknownSourceError from error
