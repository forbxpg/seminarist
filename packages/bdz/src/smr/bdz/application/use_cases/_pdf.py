"""Store a PDF and count its pages, deleting it when it does not qualify."""

from __future__ import annotations

import asyncio
from datetime import datetime

from smr.bdz.domain import NotAPdfError, TooManyPagesError
from smr.core.files import (
    FileKind,
    FileStore,
    PdfBrokenError,
    PdfLockedError,
    StoredFile,
    UnsupportedFileError,
)
from smr.core.files.pdf import count_pages


async def store_pdf(
    files: FileStore,
    data: bytes,
    now: datetime,
    max_pages: int,
) -> tuple[StoredFile, int]:
    """Save a PDF and count its pages.

    Args:
        files: FileStore - Where files live.
        data: bytes - The PDF.
        now: datetime - Names the month folder.
        max_pages: int - The most pages a БДЗ accepts.

    Returns:
        tuple[StoredFile, int] - Where it went, and how many pages it has.

    Raises:
        NotAPdfError: If the bytes are not a PDF.
        TooManyPagesError: If it has too many pages.
        PdfLockedError: If it asks for a password.
        PdfBrokenError: If it does not open.

    """
    try:
        saved = await files.save(data, accepted={FileKind.PDF}, now=now)
    except UnsupportedFileError as error:
        raise NotAPdfError from error
    try:
        # pdfium parses up to 20 MB here; keep it off the bot's event loop.
        pages = await asyncio.to_thread(count_pages, data)
    except (PdfLockedError, PdfBrokenError):
        await files.delete(saved.relative_path)
        raise
    if pages > max_pages:
        await files.delete(saved.relative_path)
        raise TooManyPagesError
    return saved, pages
