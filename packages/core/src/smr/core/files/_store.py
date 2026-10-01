"""Store files under the data directory by uuid, with the extension of their kind."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from ._errors import FileTooLargeError, UnsupportedFileError
from ._sniff import sniff

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime
    from pathlib import Path

    from ._kinds import FileKind

_FILES_DIR = "files"


@dataclass(frozen=True, slots=True)
class StoredFile:
    """A file written to disk.

    Attributes:
        relative_path: str - Path under the data directory, POSIX style.
        kind: FileKind - What the bytes are.
        size: int - Bytes.
        sha256: str - Hex digest, to spot the same file sent twice.

    """

    relative_path: str
    kind: FileKind
    size: int
    sha256: str


@final
class FileStore:
    """Files of the seminars under one data directory.

    Neither a person's name nor the sender's file name ever reaches the disk: the path
    is a month folder and a uuid, the extension comes from the sniffed kind.
    """

    def __init__(self, data_dir: Path, max_bytes: int) -> None:
        self._data_dir: Path = data_dir
        self._max_bytes: int = max_bytes

    async def save(
        self,
        data: bytes,
        *,
        accepted: Collection[FileKind],
        now: datetime,
    ) -> StoredFile:
        """Check a file and write it.

        Args:
            data: bytes - The whole file.
            accepted: Collection[FileKind] - Kinds allowed here.
            now: datetime - When; names the month folder.

        Returns:
            StoredFile - Where it went and what it is.

        Raises:
            FileTooLargeError: If it is larger than the store accepts.
            UnsupportedFileError: If its bytes are not of an accepted kind.

        """
        if len(data) > self._max_bytes:
            raise FileTooLargeError
        kind = sniff(data)
        if kind is None or kind not in accepted:
            raise UnsupportedFileError
        relative = f"{_FILES_DIR}/{now:%Y-%m}/{uuid.uuid4().hex}.{kind.value}"
        target = self._data_dir / relative
        await asyncio.to_thread(_write, target, data)
        return StoredFile(
            relative_path=relative,
            kind=kind,
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def path(self, relative_path: str) -> Path:
        """Resolve a stored file's absolute path.

        Args:
            relative_path: str - Path the store returned.

        Returns:
            Path - Absolute path; it may no longer exist.

        Raises:
            ValueError: If the path leaves the files directory.

        """
        root = (self._data_dir / _FILES_DIR).resolve()
        target = (self._data_dir / relative_path).resolve()
        if not target.is_relative_to(root):
            msg = "the path leaves the files directory"
            raise ValueError(msg)
        return target

    async def delete(self, relative_path: str) -> None:
        """Delete a stored file; a missing one is not an error.

        Args:
            relative_path: str - Path the store returned.

        """
        target = self.path(relative_path)
        await asyncio.to_thread(target.unlink, missing_ok=True)


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = target.write_bytes(data)
