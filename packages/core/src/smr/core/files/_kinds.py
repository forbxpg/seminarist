"""Kinds of file the seminars accept."""

from __future__ import annotations

from enum import StrEnum


class FileKind(StrEnum):
    """A file kind; its value is the extension the file is stored with."""

    JPEG = "jpg"
    PNG = "png"
    WEBP = "webp"
    HEIC = "heic"
    PDF = "pdf"
    DOCX = "docx"

    @property
    def is_image(self) -> bool:
        """Tell whether Telegram can show the file as a photo.

        Returns:
            bool - True for JPEG, PNG and WEBP.

        """
        return self in {FileKind.JPEG, FileKind.PNG, FileKind.WEBP}
