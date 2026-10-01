"""Tell a file's kind by its first bytes, never by its name or claimed type."""

from __future__ import annotations

import io
import zipfile

from ._kinds import FileKind

_HEIC_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"})
# A DOCX is a ZIP holding a Word document; other ZIPs (archives, XLSX) are refused.
_DOCX_PARTS = frozenset({"[Content_Types].xml", "word/document.xml"})


def sniff(data: bytes) -> FileKind | None:
    """Recognise the kind of a file from its content.

    Args:
        data: bytes - The whole file.

    Returns:
        FileKind | None - Its kind, or None when it is not one the seminars accept.

    """
    kind: FileKind | None = None
    if data.startswith(b"\xff\xd8\xff"):
        kind = FileKind.JPEG
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = FileKind.PNG
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = FileKind.WEBP
    elif data[4:8] == b"ftyp" and data[8:12] in _HEIC_BRANDS:
        kind = FileKind.HEIC
    elif data.startswith(b"%PDF-"):
        kind = FileKind.PDF
    elif data.startswith(b"PK\x03\x04") and _is_docx(data):
        kind = FileKind.DOCX
    return kind


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return set(archive.namelist()) >= _DOCX_PARTS
    except zipfile.BadZipFile:
        return False
