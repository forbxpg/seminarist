"""Files leave the disk: a student forgotten or removed, a group purged; and exports."""

from __future__ import annotations

import asyncio
import zipfile
from typing import TYPE_CHECKING, final

from smr.core.clock import MOSCOW
from smr.homework.domain import folder_name

from ._common import assignment_of

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from pathlib import Path

    from smr.core.access import AdminGuard
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.core.files import FileStore
    from smr.homework.application.ports import (
        AssignmentRepository,
        FileRepository,
        SubmissionRepository,
    )
    from smr.roster.application.contracts import RosterApi

_EXPORTS = "exports"


@final
class DeleteStudentFiles:
    """Every file a student sent is deleted from disk and from the database."""

    def __init__(
        self,
        stored: FileRepository,
        files: FileStore,
        uow: UnitOfWork,
    ) -> None:
        self._stored: FileRepository = stored
        self._files: FileStore = files
        self._uow: UnitOfWork = uow

    async def __call__(self, student_ids: Sequence[uuid.UUID]) -> int:
        """Delete them.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            int - How many files were deleted.

        """
        async with self._uow:
            paths = await self._stored.delete_of_students(student_ids)
            await self._uow.commit()
        for path in paths:
            await self._files.delete(path)
        return len(paths)


@final
class DeleteGroupFiles:
    """Before a group is purged, its files leave the disk."""

    def __init__(self, stored: FileRepository, files: FileStore) -> None:
        self._stored: FileRepository = stored
        self._files: FileStore = files

    async def __call__(self, group_id: uuid.UUID) -> int:
        """Delete them; the rows go with the group.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            int - How many files were deleted.

        """
        paths = await self._stored.paths_of_group(group_id)
        for path in paths:
            await self._files.delete(path)
        return len(paths)


@final
class ExportSubmissions:
    """A zip of an assignment's live work, one folder per student name."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        stored: FileRepository,
        roster: RosterApi,
        files: FileStore,
        guard: AdminGuard,
        clock: Clock,
        data_dir: Path,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._stored: FileRepository = stored
        self._roster: RosterApi = roster
        self._files: FileStore = files
        self._guard: AdminGuard = guard
        self._clock: Clock = clock
        self._data_dir: Path = data_dir

    async def __call__(self, actor: int, assignment_id: uuid.UUID) -> Path:
        """Build it.

        Args:
            actor: int - Teacher's Telegram id.
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Path - The zip under the exports folder.

        """
        self._guard.require(actor)
        assignment = await assignment_of(self._assignments, assignment_id)
        members: list[tuple[Path, str]] = []
        for submission in await self._submissions.live_of_assignment(assignment_id):
            student = await self._roster.student(submission.student_id)
            if student is None:
                continue
            folder = folder_name(student.full_name)
            for file in await self._stored.of_submission(submission.submission_id):
                arcname = f"{folder}/{file.position:02d}.{file.kind.value}"
                members.append((self._files.path(file.path), arcname))
        stamp = self._clock.now().astimezone(MOSCOW)
        target = (
            self._data_dir
            / _EXPORTS
            / f"{folder_name(assignment.title)} {stamp:%Y-%m-%d %H-%M}.zip"
        )
        await asyncio.to_thread(_zip, target, members)
        return target


def _zip(target: Path, members: list[tuple[Path, str]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, arcname in members:
            if source.exists():
                archive.write(source, arcname)
