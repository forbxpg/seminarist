"""Files of the seminars on disk: stored by uuid, typed by their bytes."""

from __future__ import annotations

from ._errors import (
    FilesError,
    FileTooLargeError,
    PdfBrokenError,
    PdfLockedError,
    UnsupportedFileError,
)
from ._kinds import FileKind
from ._sniff import sniff
from ._store import FileStore, StoredFile

__all__ = (
    "FileKind",
    "FileStore",
    "FileTooLargeError",
    "FilesError",
    "PdfBrokenError",
    "PdfLockedError",
    "StoredFile",
    "UnsupportedFileError",
    "sniff",
)
