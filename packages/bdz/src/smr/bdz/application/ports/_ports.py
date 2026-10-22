"""Ports of БДЗ: where assignments and versions are stored."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.bdz.domain import Bdz, BdzSubmission
    from smr.review.domain import SchemeTask


class AssignmentRepository(Protocol):
    """Every БДЗ and its point scheme."""

    async def add(self, bdz: Bdz, tasks: Sequence[SchemeTask]) -> None:
        """Store a БДЗ and its scheme.

        Args:
            bdz: Bdz - The assignment.
            tasks: Sequence[SchemeTask] - Its tasks.

        """
        ...

    async def get(self, bdz_id: uuid.UUID) -> Bdz | None:
        """Read a БДЗ.

        Args:
            bdz_id: uuid.UUID - It.

        Returns:
            Bdz | None - None when unknown.

        """
        ...

    async def tasks(self, bdz_id: uuid.UUID) -> tuple[SchemeTask, ...]:
        """Read the scheme.

        Args:
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            tuple[SchemeTask, ...] - The tasks, in order.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Bdz]:
        """List a group's БДЗ, newest first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Bdz] - The assignments.

        """
        ...

    async def save_deadline(self, bdz: Bdz) -> None:
        """Store a new deadline.

        Args:
            bdz: Bdz - The assignment with the new deadline.

        """
        ...

    async def save_work_type(self, bdz: Bdz) -> None:
        """Store a new work type.

        Args:
            bdz: Bdz - The assignment with the new work type.

        """
        ...

    async def delete(self, bdz_id: uuid.UUID) -> Bdz | None:
        """Delete a БДЗ. Submissions cascade.

        Args:
            bdz_id: uuid.UUID - It.

        Returns:
            Bdz | None - What was deleted.

        """
        ...


class SubmissionRepository(Protocol):
    """Every version of every student's БДЗ."""

    async def add(self, submission: BdzSubmission) -> None:
        """Store a version.

        Args:
            submission: BdzSubmission - It.

        """
        ...

    async def get(
        self,
        submission_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> BdzSubmission | None:
        """Read a version.

        Args:
            submission_id: uuid.UUID - It.
            lock: bool - Lock the row when true.

        Returns:
            BdzSubmission | None - None when unknown.

        """
        ...

    async def live(
        self,
        bdz_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> BdzSubmission | None:
        """Read the live version of a student.

        Args:
            bdz_id: uuid.UUID - The БДЗ.
            student_id: uuid.UUID - The student.
            lock: bool - Lock the row when true.

        Returns:
            BdzSubmission | None - None when they have not sent one.

        """
        ...

    async def live_all(self) -> Sequence[BdzSubmission]:
        """List every live version, oldest first.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        ...

    async def of_bdz(self, bdz_id: uuid.UUID) -> Sequence[BdzSubmission]:
        """List every version of a БДЗ.

        Args:
            bdz_id: uuid.UUID - The БДЗ.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        ...

    async def of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[BdzSubmission]:
        """List every version of these students.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[BdzSubmission] - The versions.

        """
        ...

    async def next_version(self, bdz_id: uuid.UUID, student_id: uuid.UUID) -> int:
        """Tell the next version number.

        Args:
            bdz_id: uuid.UUID - The БДЗ.
            student_id: uuid.UUID - The student.

        Returns:
            int - One more than the highest version, or 1.

        """
        ...

    async def supersede(self, submission_id: uuid.UUID) -> None:
        """Mark a version superseded.

        Args:
            submission_id: uuid.UUID - It.

        """
        ...
