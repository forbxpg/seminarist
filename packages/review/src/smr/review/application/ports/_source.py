"""A source of work the review can grade, without knowing what the work is."""

from __future__ import annotations

import uuid  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from collections.abc import Sequence  # ruff: ignore[typing-only-standard-library-import] -- protocol method
from dataclasses import dataclass
from datetime import datetime  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from decimal import Decimal  # ruff: ignore[typing-only-standard-library-import] -- dataclass field type
from typing import Protocol

from smr.review.domain import SchemeTask  # ruff: ignore[typing-only-first-party-import] -- dataclass field type


@dataclass(frozen=True, slots=True)
class WorkRef:
    """One live version a source offers for review.

    Attributes:
        work_id: uuid.UUID - The version.
        task_ref: uuid.UUID - The assignment.
        student_ref: uuid.UUID - The roster row.
        version: int - 1, 2, …
        sha256: str - The file.
        pages: int - How many pages it has.
        sent_at: datetime - When the student sent it.
        is_late: bool - Sent after the deadline.
        title: str - The assignment's title.
        journal_no: int | None - The student's number in the group's journal, which
            picks their variant; None when the teacher has not set it.

    """

    work_id: uuid.UUID
    task_ref: uuid.UUID
    student_ref: uuid.UUID
    version: int
    sha256: str
    pages: int
    sent_at: datetime
    is_late: bool
    title: str
    journal_no: int | None = None


@dataclass(frozen=True, slots=True)
class TaskSheet:
    """The point scheme and the files of an assignment.

    Attributes:
        task_ref: uuid.UUID - The assignment.
        title: str - Its title.
        scheme: tuple[SchemeTask, ...] - Its tasks.
        max_points: Decimal - The sum.
        statement_path: str - The statement, a FileStore path.
        statement_pages: int - How many pages it has.
        solutions_path: str - The solutions, never sent to students.
        solutions_pages: int - How many pages they have.

    """

    task_ref: uuid.UUID
    title: str
    scheme: tuple[SchemeTask, ...]
    max_points: Decimal
    statement_path: str
    statement_pages: int
    solutions_path: str
    solutions_pages: int


class ReviewSource(Protocol):
    """Work a feature offers to the review. The review does not import the feature."""

    name: str

    async def live_works(self) -> Sequence[WorkRef]:
        """List live versions of active groups, oldest first.

        Returns:
            Sequence[WorkRef] - The versions.

        """
        ...

    async def work(
        self,
        work_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> WorkRef | None:
        """Read one live version.

        Args:
            work_id: uuid.UUID - The version.
            lock: bool - Take a row lock when true.

        Returns:
            WorkRef | None - None when missing, not live, or the group is archived.

        """
        ...

    async def sheet(self, task_ref: uuid.UUID) -> TaskSheet:
        """Read an assignment's scheme and files.

        Args:
            task_ref: uuid.UUID - The assignment.

        Returns:
            TaskSheet - The scheme.

        """
        ...

    async def work_path(self, work_id: uuid.UUID) -> str:
        """Tell where the version's PDF is stored.

        Args:
            work_id: uuid.UUID - The version.

        Returns:
            str - A FileStore path.

        """
        ...

    async def belongs_to(self, work_id: uuid.UUID, tg_user_id: int) -> bool:
        """Tell whether the account owns the version.

        Args:
            work_id: uuid.UUID - The version.
            tg_user_id: int - The account.

        Returns:
            bool - True when it is the account's approved row.

        """
        ...

    async def apply_grade(
        self,
        work_id: uuid.UUID,
        total: Decimal,
        *,
        teacher: int | None,
        agent: str | None,
    ) -> None:
        """Write the total into the ledger.

        Args:
            work_id: uuid.UUID - The version.
            total: Decimal - The points.
            teacher: int | None - The teacher's Telegram id.
            agent: str | None - The model's name.

        """
        ...
