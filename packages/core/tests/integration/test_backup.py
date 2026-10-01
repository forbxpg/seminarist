"""A backup of a real database."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from smr.core.backup import Backup, BackupError
from smr.core.clock import FixedClock

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("pg_dump") is None,
        reason="pg_dump is not installed",
    ),
]


async def test_backup_dumps_and_keeps_the_newest(
    database_url: str,
    tmp_path: Path,
) -> None:
    """Each copy holds a dump and the files; only the newest copies are kept."""
    data = tmp_path / "data"
    (data / "files").mkdir(parents=True)
    (data / "files" / "a.pdf").write_bytes(b"%PDF-1.7\n")
    clock = FixedClock(datetime(2026, 10, 2, tzinfo=UTC))
    backup = Backup(database_url, data, tmp_path / "backups", clock, keep=2)
    made = []
    for _ in range(3):
        made.append(await backup())
        clock.advance(timedelta(minutes=1))
    assert not made[0].exists()
    assert (made[2] / "database.dump").stat().st_size > 0
    assert (made[2] / "files.tar.gz").exists()


async def test_a_failed_dump_leaves_nothing(tmp_path: Path) -> None:
    """A dump of an unreachable database fails and removes its folder."""
    clock = FixedClock(datetime(2026, 10, 2, tzinfo=UTC))
    url = "postgresql+asyncpg://nobody:x@127.0.0.1:1/none"
    backup = Backup(url, tmp_path, tmp_path / "backups", clock)
    with pytest.raises(BackupError):
        await backup()
    assert list((tmp_path / "backups").iterdir()) == []
