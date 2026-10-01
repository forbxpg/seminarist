"""Dump the database with pg_dump and pack the files, keeping the newest copies."""

from __future__ import annotations

import asyncio
import os
import shutil
import tarfile
from typing import TYPE_CHECKING, final
from urllib.parse import unquote, urlsplit

from smr.core.clock import MOSCOW

if TYPE_CHECKING:
    from pathlib import Path

    from smr.core.clock import Clock

_FILES = "files"
_PREFIX = "backup-"


class BackupError(Exception):
    """pg_dump failed; the half-written copy was removed."""


@final
class Backup:
    """One folder per copy: `database.dump` (pg_dump custom format), `files.tar.gz`."""

    def __init__(
        self,
        database_url: str,
        data_dir: Path,
        backup_dir: Path,
        clock: Clock,
        keep: int = 14,
    ) -> None:
        self._database_url: str = database_url
        self._data_dir: Path = data_dir
        self._backup_dir: Path = backup_dir
        self._clock: Clock = clock
        self._keep: int = keep

    async def __call__(self) -> Path:
        """Make a copy and drop the oldest beyond the limit.

        Returns:
            Path - The new copy's folder.

        Raises:
            BackupError: If pg_dump fails.

        """
        stamp = self._clock.now().astimezone(MOSCOW)
        target = self._backup_dir / f"{_PREFIX}{stamp:%Y-%m-%d_%H%M%S}"
        target.mkdir(parents=True, exist_ok=False)
        try:
            await self._dump(target / "database.dump")
            await asyncio.to_thread(
                _pack,
                self._data_dir / _FILES,
                target / "files.tar.gz",
            )
        except BackupError:
            await asyncio.to_thread(shutil.rmtree, target, ignore_errors=True)
            raise
        await asyncio.to_thread(self._prune)
        return target

    async def _dump(self, target: Path) -> None:
        parts = urlsplit(self._database_url.replace("+asyncpg", "", 1))
        # The password goes through the environment, never the command line.
        environment = {**os.environ, "PGPASSWORD": unquote(parts.password or "")}
        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--format=custom",
            "--no-owner",
            f"--host={parts.hostname or 'localhost'}",
            f"--port={parts.port or 5432}",
            f"--username={unquote(parts.username or '')}",
            f"--dbname={parts.path.lstrip('/')}",
            f"--file={target}",
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, error = await process.communicate()
        if process.returncode != 0:
            raise BackupError(error.decode(errors="replace").strip()[:500])

    def _prune(self) -> None:
        copies = sorted(
            path
            for path in self._backup_dir.iterdir()
            if path.is_dir() and path.name.startswith(_PREFIX)
        )
        for old in copies[: max(len(copies) - self._keep, 0)]:
            shutil.rmtree(old, ignore_errors=True)


def _pack(source: Path, target: Path) -> None:
    with tarfile.open(target, "w:gz") as archive:
        if source.exists():
            archive.add(source, arcname=_FILES)
