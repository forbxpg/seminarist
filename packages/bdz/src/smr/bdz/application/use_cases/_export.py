"""A zip of the live PDFs and the current verdicts."""

from __future__ import annotations

import asyncio
import uuid
import zipfile
from pathlib import Path
from typing import final

from smr.bdz.domain import BdzNotFoundError, SubmissionStatus, folder_name
from smr.bdz.infrastructure.repositories import (
    SqlAlchemyAssignments,
    SqlAlchemySubmissions,
)
from smr.core.access import AdminGuard
from smr.core.clock import MOSCOW, Clock
from smr.core.files import FileStore
from smr.review.application.contracts import ReviewApi
from smr.review.domain import Verdict
from smr.roster.application.contracts import RosterApi

_EXPORTS = "exports"


@final
class ExportBdz:
    """One folder per student: the live PDF and a text of the current verdict."""

    def __init__(
        self,
        assignments: SqlAlchemyAssignments,
        submissions: SqlAlchemySubmissions,
        roster: RosterApi,
        reviews: ReviewApi,
        files: FileStore,
        guard: AdminGuard,
        clock: Clock,
        data_dir: Path,
    ) -> None:
        self._assignments: SqlAlchemyAssignments = assignments
        self._submissions: SqlAlchemySubmissions = submissions
        self._roster: RosterApi = roster
        self._reviews: ReviewApi = reviews
        self._files: FileStore = files
        self._guard: AdminGuard = guard
        self._clock: Clock = clock
        self._data_dir: Path = data_dir

    async def __call__(self, actor: int, bdz_id: uuid.UUID) -> Path:
        """Build it.

        Args:
            actor: int - Teacher's Telegram id.
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            Path - The zip under the exports folder.

        Raises:
            BdzNotFoundError: If there is no such БДЗ.

        """
        self._guard.require(actor)
        found = await self._assignments.get(bdz_id)
        if found is None:
            raise BdzNotFoundError
        files: list[tuple[Path, str]] = []
        notes: list[tuple[str, str]] = []
        for row in await self._submissions.of_bdz(bdz_id):
            if row.status is not SubmissionStatus.LIVE:
                continue
            student = await self._roster.student(row.student_id)
            if student is None:
                continue
            folder = folder_name(student.full_name)
            files.append((self._files.path(row.path), f"{folder}/работа.pdf"))
            verdict = await self._reviews.current("bdz", row.submission_id)
            notes.append((f"{folder}/разбор.txt", _report(verdict)))
        stamp = self._clock.now().astimezone(MOSCOW)
        target = (
            self._data_dir
            / _EXPORTS
            / f"{folder_name(found.title)} {stamp:%Y-%m-%d %H-%M}.zip"
        )
        await asyncio.to_thread(_zip, target, files, notes)
        return target


def _report(verdict: Verdict | None) -> str:
    if verdict is None:
        return "Проверки пока нет.\n"
    lines = [f"Итог: {verdict.total} из {verdict.max_points}", ""]
    if verdict.summary:
        lines.extend((verdict.summary, ""))
    for task in verdict.tasks:
        lines.append(f"Задача {task.number}: {task.points}")
        if task.explanation:
            lines.append(task.explanation)
        lines.append("")
    return "\n".join(lines)


def _zip(
    target: Path,
    files: list[tuple[Path, str]],
    notes: list[tuple[str, str]],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, arcname in files:
            if source.exists():
                archive.write(source, arcname)
        for arcname, text in notes:
            archive.writestr(arcname, text)
