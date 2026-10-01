"""Ports of homework."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.homework.domain import Assignment, Submission, SubmissionFile


class AssignmentRepository(Protocol):
    """Every assignment."""

    async def add(self, assignment: Assignment) -> None:
        """Add an assignment.

        Args:
            assignment: Assignment - It.

        """
        ...

    async def get(self, assignment_id: uuid.UUID) -> Assignment | None:
        """Read an assignment.

        Args:
            assignment_id: uuid.UUID - It.

        Returns:
            Assignment | None - It, or None.

        """
        ...

    async def of_group(self, group_id: uuid.UUID) -> Sequence[Assignment]:
        """List a group's assignments, the latest deadline first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Assignment] - Its assignments.

        """
        ...

    async def update(self, assignment: Assignment) -> None:
        """Store a changed assignment.

        Args:
            assignment: Assignment - It, changed.

        """
        ...

    async def delete(self, assignment_id: uuid.UUID) -> None:
        """Delete an assignment with its submissions.

        Args:
            assignment_id: uuid.UUID - It.

        """
        ...


class SubmissionRepository(Protocol):
    """Every version of every student's work."""

    async def add(self, submission: Submission) -> None:
        """Add a version.

        Args:
            submission: Submission - It.

        """
        ...

    async def get(
        self,
        submission_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Submission | None:
        """Read a version.

        Args:
            submission_id: uuid.UUID - It.
            lock: bool - Lock the row until the transaction ends.

        Returns:
            Submission | None - It, or None.

        """
        ...

    async def draft(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> Submission | None:
        """Find a student's draft.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.

        Returns:
            Submission | None - The draft, or None.

        """
        ...

    async def live(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Submission | None:
        """Find a student's submitted or graded version.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.
            lock: bool - Lock the row until the transaction ends.

        Returns:
            Submission | None - It, or None.

        """
        ...

    async def next_version(
        self,
        assignment_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> int:
        """Tell the number of a student's next version.

        Args:
            assignment_id: uuid.UUID - The assignment.
            student_id: uuid.UUID - The student.

        Returns:
            int - One more than the highest so far, 1 for the first.

        """
        ...

    async def live_of_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> Sequence[Submission]:
        """List the live versions of an assignment.

        Args:
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Sequence[Submission] - Submitted or graded versions.

        """
        ...

    async def waiting(self, group_id: uuid.UUID) -> Sequence[Submission]:
        """List a group's submitted, ungraded versions, the earliest sent first.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Submission] - The queue.

        """
        ...

    async def update(self, submission: Submission) -> None:
        """Store a changed version.

        Args:
            submission: Submission - It, changed.

        """
        ...

    async def delete(self, submission_id: uuid.UUID) -> None:
        """Delete a version with its files' rows.

        Args:
            submission_id: uuid.UUID - It.

        """
        ...


class FileRepository(Protocol):
    """Every file of every submission."""

    async def add(self, file: SubmissionFile) -> None:
        """Add a file.

        Args:
            file: SubmissionFile - It.

        """
        ...

    async def of_submission(self, submission_id: uuid.UUID) -> Sequence[SubmissionFile]:
        """List a version's files in order.

        Args:
            submission_id: uuid.UUID - The version.

        Returns:
            Sequence[SubmissionFile] - Its files.

        """
        ...

    async def paths_of_assignment(self, assignment_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of an assignment's files, its statement included.

        Args:
            assignment_id: uuid.UUID - The assignment.

        Returns:
            Sequence[str] - The paths.

        """
        ...

    async def delete_of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[str]:
        """Delete the rows of students' files.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[str] - The stored paths of the deleted rows.

        """
        ...

    async def delete_of_submission(self, submission_id: uuid.UUID) -> Sequence[str]:
        """Delete the rows of a version's files.

        Args:
            submission_id: uuid.UUID - The version.

        Returns:
            Sequence[str] - The stored paths of the deleted rows.

        """
        ...

    async def paths_of_students(
        self,
        student_ids: Sequence[uuid.UUID],
    ) -> Sequence[str]:
        """List the stored paths of students' files.

        Args:
            student_ids: Sequence[uuid.UUID] - The students.

        Returns:
            Sequence[str] - The paths.

        """
        ...

    async def paths_of_group(self, group_id: uuid.UUID) -> Sequence[str]:
        """List the stored paths of a group's files, statements included.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[str] - The paths.

        """
        ...
