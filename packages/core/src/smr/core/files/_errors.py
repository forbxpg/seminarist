"""Errors of the file store."""

from __future__ import annotations


class FilesError(Exception):
    """Base of the file store's errors."""


class UnsupportedFileError(FilesError):
    """The bytes are not of an accepted kind, whatever the file is called."""


class FileTooLargeError(FilesError):
    """The file is larger than the store accepts."""


class PdfLockedError(FilesError):
    """The PDF asks for a password."""


class PdfBrokenError(FilesError):
    """The PDF does not open, or it has no pages."""
