"""A seminar card and its files."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from enum import StrEnum

from smr.core.files import FileKind  # ruff: ignore[typing-only-first-party-import] -- dataclass field type


class MaterialStatus(StrEnum):
    """Whether students see the card."""

    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class Material:
    """A card such as "Семинар 4".

    Attributes:
        material_id: uuid.UUID - The card.
        group_id: uuid.UUID - Its group.
        title: str - Its title.
        status: MaterialStatus - Draft or published.
        published_at: datetime | None - When it was published.
        created_at: datetime - When it was created.

    """

    material_id: uuid.UUID
    group_id: uuid.UUID
    title: str
    status: MaterialStatus
    published_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MaterialFile:
    """A file of a card.

    Attributes:
        file_id: uuid.UUID - The file.
        material_id: uuid.UUID - Its card.
        tg_file_id: str - Telegram's id, to send it again.
        path: str - Where it is on disk.
        kind: FileKind - What it is.
        size: int - Bytes.
        position: int - Order in the card.

    """

    file_id: uuid.UUID
    material_id: uuid.UUID
    tg_file_id: str
    path: str
    kind: FileKind
    size: int
    position: int
