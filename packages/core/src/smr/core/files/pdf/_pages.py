"""Open a PDF's pages. pdfium is not thread-safe, so one lock covers every call."""

from __future__ import annotations

import asyncio
import io
import threading
from typing import TYPE_CHECKING, cast

import pypdfium2 as pdfium
from pypdfium2 import PdfiumError

from smr.core.files import PdfBrokenError, PdfLockedError

if TYPE_CHECKING:
    from pathlib import Path

    from PIL import Image

# ponytail: one global pdfium lock, per-process pool if review gets slow
_PDFIUM = threading.Lock()
_SCALE = 150 / 72
_LONGEST_SIDE = 2000
_JPEG_QUALITY = 85
_MAX_COUNT = 6


def count_pages(data: bytes) -> int:
    """Count the pages of a PDF.

    Args:
        data: bytes - The whole file.

    Returns:
        int - How many pages it has, at least one.

    Raises:
        PdfLockedError: If the PDF asks for a password.
        PdfBrokenError: If it does not open, or it has no pages.

    """
    with _PDFIUM:
        try:
            pages = _count_pages(data)
        except PdfiumError as error:
            if "password" in str(error).lower():
                raise PdfLockedError from error
            raise PdfBrokenError from error
    if pages < 1:
        raise PdfBrokenError
    return pages


async def render_pages(path: Path, start: int, count: int) -> list[bytes]:
    """Render a window of pages to JPEG bytes.

    Args:
        path: Path - The PDF.
        start: int - The first page, counting from 1.
        count: int - How many pages to render, from 1 to 6. A window that runs past
            the last page is clipped to it.

    Returns:
        list[bytes] - One JPEG per page, longest side at most 2000 pixels.

    Raises:
        ValueError: If `start` is past the last page or `count` is outside 1..6.
        PdfLockedError: If the PDF asks for a password.
        PdfBrokenError: If it does not open.

    """
    if count < 1 or count > _MAX_COUNT:
        msg = "count is from 1 to 6"
        raise ValueError(msg)
    try:
        return await asyncio.to_thread(_render_pages, path, start, count)
    except PdfiumError as error:
        if "password" in str(error).lower():
            raise PdfLockedError from error
        raise PdfBrokenError from error


def _count_pages(data: bytes) -> int:
    """Count pages, leaving a locked or broken file as `PdfiumError`.

    Args:
        data: bytes - The whole file.

    Returns:
        int - How many pages pdfium reports.

    """
    document = pdfium.PdfDocument(data)
    try:
        return len(document)
    finally:
        _ = document.close()


def _render_pages(path: Path, start: int, count: int) -> list[bytes]:
    """Render under the pdfium lock. A locked or broken file stays a `PdfiumError`.

    Args:
        path: Path - The PDF.
        start: int - The first page, counting from 1.
        count: int - How many pages were asked for.

    Returns:
        list[bytes] - One JPEG per rendered page.

    Raises:
        ValueError: If `start` is past the last page.

    """
    with _PDFIUM:
        document = pdfium.PdfDocument(path)
        try:
            last = len(document)
            if start < 1 or start > last:
                msg = "start is past the last page"
                raise ValueError(msg)
            end = min(start + count - 1, last)
            return [_jpeg(document, number) for number in range(start, end + 1)]
        finally:
            _ = document.close()


def _jpeg(document: pdfium.PdfDocument, number: int) -> bytes:
    """Render one page.

    Args:
        document: pdfium.PdfDocument - The open PDF.
        number: int - The page, counting from 1.

    Returns:
        bytes - JPEG bytes.

    """
    page = document[number - 1]
    # The stub types scale as int and the bitmap as unknown; pdfium takes 150/72.
    bitmap = page.render(scale=_SCALE)  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
    try:
        image = cast("Image.Image", bitmap.to_pil())  # pyright: ignore[reportUnknownMemberType]
        image.thumbnail((_LONGEST_SIDE, _LONGEST_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
        return buffer.getvalue()
    finally:
        bitmap.close()  # pyright: ignore[reportUnknownMemberType]
        _ = page.close()
