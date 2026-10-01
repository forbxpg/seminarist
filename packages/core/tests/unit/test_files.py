"""Recognising and storing files."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from smr.core.files import (
    FileKind,
    FileStore,
    FileTooLargeError,
    UnsupportedFileError,
    sniff,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 10, 2, tzinfo=UTC)


def _zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "x")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"\xff\xd8\xff\xe0rest", FileKind.JPEG),
        (b"\x89PNG\r\n\x1a\nrest", FileKind.PNG),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", FileKind.WEBP),
        (b"\x00\x00\x00\x18ftypheic\x00\x00", FileKind.HEIC),
        (b"%PDF-1.7\n", FileKind.PDF),
        (_zip("[Content_Types].xml", "word/document.xml"), FileKind.DOCX),
    ],
)
def test_recognises_accepted_kinds(data: bytes, kind: FileKind) -> None:
    """Each accepted kind is told by its bytes."""
    assert sniff(data) is kind


@pytest.mark.parametrize(
    "data",
    [
        b"MZ\x90\x00 an executable called homework.pdf",
        _zip("evil.exe"),
        _zip("[Content_Types].xml", "xl/workbook.xml"),
        b"PK\x03\x04 broken zip",
        b"",
    ],
)
def test_refuses_everything_else(data: bytes) -> None:
    """An executable, an archive or a spreadsheet is not accepted."""
    assert sniff(data) is None


async def test_stores_by_uuid_with_the_sniffed_extension(tmp_path: Path) -> None:
    """The path carries neither the sender's name nor the claimed type."""
    store = FileStore(tmp_path, max_bytes=1024)
    stored = await store.save(b"%PDF-1.7\n", accepted=set(FileKind), now=_NOW)
    assert stored.relative_path.startswith("files/2026-10/")
    assert stored.relative_path.endswith(".pdf")
    assert store.path(stored.relative_path).read_bytes() == b"%PDF-1.7\n"
    await store.delete(stored.relative_path)
    assert not store.path(stored.relative_path).exists()


async def test_refuses_a_kind_not_accepted_here(tmp_path: Path) -> None:
    """A PDF is refused where only images are accepted."""
    store = FileStore(tmp_path, max_bytes=1024)
    with pytest.raises(UnsupportedFileError):
        await store.save(b"%PDF-1.7\n", accepted={FileKind.JPEG}, now=_NOW)


async def test_refuses_a_large_file(tmp_path: Path) -> None:
    """A file over the limit is refused before it is looked at."""
    store = FileStore(tmp_path, max_bytes=4)
    with pytest.raises(FileTooLargeError):
        await store.save(b"%PDF-1.7\n", accepted=set(FileKind), now=_NOW)


def test_refuses_a_path_outside_the_files(tmp_path: Path) -> None:
    """A stored path cannot climb out of the files directory."""
    store = FileStore(tmp_path, max_bytes=4)
    with pytest.raises(ValueError, match="leaves"):
        store.path("files/../../etc/passwd")
