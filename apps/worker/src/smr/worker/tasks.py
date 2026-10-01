"""The tasks: plain functions, injected by dishka, registered by the broker module."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from dishka.integrations.taskiq import FromDishka, inject

from smr.core.backup import Backup
from smr.core.clock import Clock
from smr.core.config import StorageSettings
from smr.homework.application.use_cases import DeleteGroupFiles, QueueReminders
from smr.materials.application.use_cases import DeleteGroupMaterialFiles
from smr.notifications.application.use_cases import DeliverPending, PurgeOutbox
from smr.roster.application.use_cases import GroupsDueForPurge, PurgeGroup

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

EXPORTS_KEPT = timedelta(days=14)


@inject(patch_module=True)
async def deliver_outbox(deliver: FromDishka[DeliverPending]) -> None:
    """Send the waiting notices."""
    report = await deliver()
    if report.sent or report.failed or report.gave_up:
        logger.info(
            "outbox: sent=%d failed=%d gave_up=%d",
            report.sent,
            report.failed,
            report.gave_up,
        )


@inject(patch_module=True)
async def queue_reminders(queue: FromDishka[QueueReminders]) -> None:
    """Queue the deadline reminders that are due."""
    queued = await queue()
    if queued:
        logger.info("reminders queued: %d", queued)


@inject(patch_module=True)
async def back_up(backup: FromDishka[Backup]) -> None:
    """Back up the database and the files."""
    target = await backup()
    logger.info("backup written: %s", target.name)


@inject(patch_module=True)
async def purge_expired(
    outbox: FromDishka[PurgeOutbox],
    due: FromDishka[GroupsDueForPurge],
    homework_files: FromDishka[DeleteGroupFiles],
    material_files: FromDishka[DeleteGroupMaterialFiles],
    purge_group: FromDishka[PurgeGroup],
    storage: FromDishka[StorageSettings],
    clock: FromDishka[Clock],
) -> None:
    """Forget what has outlived its retention: notices, exports, archived groups."""
    notices = await outbox()
    exports = delete_old_exports(storage.data_dir / "exports", clock, EXPORTS_KEPT)
    groups = 0
    for group in await due():
        _ = await homework_files(group.group_id)
        _ = await material_files(group.group_id)
        await purge_group(group.group_id)
        groups += 1
    logger.info("purged: notices=%d exports=%d groups=%d", notices, exports, groups)


def delete_old_exports(folder: Path, clock: Clock, keep: timedelta) -> int:
    """Delete exports older than the retention.

    Args:
        folder: Path - The exports folder.
        clock: Clock - The clock.
        keep: timedelta - How long an export is kept.

    Returns:
        int - How many were deleted.

    """
    if not folder.exists():
        return 0
    oldest = (clock.now() - keep).timestamp()
    deleted = 0
    for path in folder.iterdir():
        if path.is_file() and path.stat().st_mtime < oldest:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted
