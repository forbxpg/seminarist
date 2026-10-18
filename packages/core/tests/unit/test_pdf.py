"""Page counts and page images of a PDF."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from PIL import Image
from pypdf import PdfWriter

from smr.core.files import PdfBrokenError, PdfLockedError
from smr.core.files.pdf import count_pages, render_pages

if TYPE_CHECKING:
    from pathlib import Path


def _pdf(pages: int, *, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if password is not None:
        writer.encrypt(password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_counts_pages() -> None:
    """Three blank pages count as three."""
    assert count_pages(_pdf(3)) == 3


def test_locked_pdf_is_refused() -> None:
    """A user password is a locked PDF, not a broken one."""
    with pytest.raises(PdfLockedError):
        count_pages(_pdf(1, password="secret"))


def test_garbage_is_broken() -> None:
    """Bytes that only start like a PDF do not open."""
    with pytest.raises(PdfBrokenError):
        count_pages(b"%PDF-1.7 garbage")


def test_zero_page_pdf_is_broken() -> None:
    """A PDF with no pages is broken."""
    with pytest.raises(PdfBrokenError):
        count_pages(_pdf(0))


async def test_renders_jpeg_pages(tmp_path: Path) -> None:
    """Pages 2 and 3 of a three-page PDF come back as capped JPEGs."""
    path = tmp_path / "work.pdf"
    path.write_bytes(_pdf(3))
    images = await render_pages(path, 2, 2)
    assert len(images) == 2
    for blob in images:
        assert blob.startswith(b"\xff\xd8")
        with Image.open(BytesIO(blob)) as picture:
            assert max(picture.size) <= 2000


async def test_render_clips_and_refuses(tmp_path: Path) -> None:
    """A window past the end is clipped; a start beyond it or a long window is refused."""
    path = tmp_path / "work.pdf"
    path.write_bytes(_pdf(3))
    assert len(await render_pages(path, 3, 6)) == 1
    with pytest.raises(ValueError, match="start"):
        await render_pages(path, 4, 1)
    with pytest.raises(ValueError, match="count"):
        await render_pages(path, 1, 7)
