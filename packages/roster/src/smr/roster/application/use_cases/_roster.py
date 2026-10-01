"""A group's roster: paste names, rename, remove."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from smr.roster.domain import (
    MAX_NAME_LENGTH,
    DuplicateNameError,
    GroupArchivedError,
    GroupNotFoundError,
    StudentNotFoundError,
    normalize_name,
    parse_roster,
)

from ._audit import by_admin
from ._results import ImportResult

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.database import UnitOfWork
    from smr.roster.application.ports import GroupRepository, StudentRepository
    from smr.roster.domain import Student


@final
class ImportRoster:
    """Names pasted one per line join a group's roster."""

    def __init__(
        self,
        groups: GroupRepository,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._groups: GroupRepository = groups
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        text: str,
    ) -> ImportResult:
        """Add them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            text: str - The pasted roster.

        Returns:
            ImportResult - How many were added and skipped.

        Raises:
            GroupNotFoundError: If there is no such group.
            GroupArchivedError: If the group is archived.

        """
        self._guard.require(actor)
        names = parse_roster(text)
        async with self._uow:
            group = await self._groups.get(group_id)
            if group is None:
                raise GroupNotFoundError
            if not group.is_active:
                raise GroupArchivedError
            added = await self._students.add_many(group_id, names)
            await self._audit.record(
                by_admin(
                    actor,
                    "roster.imported",
                    "study_group",
                    group_id,
                    after={"added": added},
                ),
            )
            await self._uow.commit()
        return ImportResult(added=added, skipped=len(names) - added)


@final
class ListStudents:
    """A group's roster for the teacher."""

    def __init__(self, students: StudentRepository, guard: AdminGuard) -> None:
        self._students: StudentRepository = students
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, group_id: uuid.UUID) -> Sequence[Student]:
        """List it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            Sequence[Student] - The roster by name.

        """
        self._guard.require(actor)
        return await self._students.of_group(group_id)


@final
class RenameStudent:
    """Fix a name typed wrong."""

    def __init__(
        self,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, student_id: uuid.UUID, full_name: str) -> None:
        """Rename the row.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The row.
            full_name: str - The new name.

        Raises:
            ValueError: If the name is empty or too long.
            StudentNotFoundError: If there is no such row.
            DuplicateNameError: If the group already has this name.

        """
        self._guard.require(actor)
        name = normalize_name(full_name)
        if not name or len(name) > MAX_NAME_LENGTH:
            msg = f"a name has 1 to {MAX_NAME_LENGTH} characters"
            raise ValueError(msg)
        async with self._uow:
            student = await self._students.get(student_id)
            if student is None:
                raise StudentNotFoundError
            roster = await self._students.of_group(student.group_id)
            if any(
                other.full_name == name and other.student_id != student_id
                for other in roster
            ):
                raise DuplicateNameError
            await self._students.rename(student_id, name)
            await self._audit.record(
                by_admin(actor, "student.renamed", "student", student_id),
            )
            await self._uow.commit()


@final
class RemoveStudent:
    """Take a row off the roster, with every grade and file tied to it."""

    def __init__(
        self,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, student_id: uuid.UUID) -> Student:
        """Remove it.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The row.

        Returns:
            Student - The removed row, to tell its account.

        Raises:
            StudentNotFoundError: If there is no such row.

        """
        self._guard.require(actor)
        async with self._uow:
            student = await self._students.get(student_id)
            if student is None:
                raise StudentNotFoundError
            await self._students.delete(student_id)
            await self._audit.record(
                by_admin(actor, "student.removed", "student", student_id),
            )
            await self._uow.commit()
        return student
