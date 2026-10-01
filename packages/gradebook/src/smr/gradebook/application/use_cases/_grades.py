"""The teacher grades: an item for the whole roster, loose points, corrections."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, final

from smr.gradebook.domain import ItemNotFoundError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence

    from smr.core.access import AdminGuard
    from smr.core.database import UnitOfWork
    from smr.gradebook.application.ports import EntryRepository, ItemRepository
    from smr.gradebook.application.services import Ledger
    from smr.gradebook.domain import GradeEntry
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Student


class _Excused(Enum):
    EXCUSED = "excused"


EXCUSED = _Excused.EXCUSED

type GradeInput = Decimal | _Excused | None
"""Points, `EXCUSED`, or None to clear the grade."""


@final
class ItemGrades:
    """An item's grades next to the roster, for the teacher to fill in."""

    def __init__(
        self,
        items: ItemRepository,
        entries: EntryRepository,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._items: ItemRepository = items
        self._entries: EntryRepository = entries
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        item_id: uuid.UUID,
        group_id: uuid.UUID,
    ) -> list[tuple[Student, GradeEntry | None]]:
        """Read them.

        Args:
            actor: int - Teacher's Telegram id.
            item_id: uuid.UUID - The item.
            group_id: uuid.UUID - Its group.

        Returns:
            list[tuple[Student, GradeEntry | None]] - Each student and their entry.

        Raises:
            ItemNotFoundError: If there is no such item.

        """
        self._guard.require(actor)
        if await self._items.get(item_id) is None:
            raise ItemNotFoundError
        by_student = {e.student_id: e for e in await self._entries.of_item(item_id)}
        return [
            (student, by_student.get(student.student_id))
            for student in await self._roster.students_of(group_id)
        ]


@final
class SetItemGrades:
    """The teacher fills in an item's grades for several students at once."""

    def __init__(self, ledger: Ledger, uow: UnitOfWork, guard: AdminGuard) -> None:
        self._ledger: Ledger = ledger
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        item_id: uuid.UUID,
        grades: Mapping[uuid.UUID, GradeInput],
    ) -> None:
        """Store them; one bad value stores none.

        Args:
            actor: int - Teacher's Telegram id.
            item_id: uuid.UUID - The item.
            grades: Mapping[uuid.UUID, GradeInput] - Each student's points,
                `EXCUSED`, or None to clear.

        """
        self._guard.require(actor)
        async with self._uow:
            for student_id, grade in grades.items():
                if grade is None:
                    await self._ledger.clear_entry(student_id, item_id, graded_by=actor)
                else:
                    excused = grade is EXCUSED
                    _ = await self._ledger.set_entry(
                        student_id,
                        item_id,
                        Decimal(0) if isinstance(grade, _Excused) else grade,
                        excused=excused,
                        comment=None,
                        graded_by=actor,
                    )
            await self._uow.commit()


@final
class AddPoints:
    """Loose points to an accumulating work type, e.g. the teacher's own mark."""

    def __init__(self, ledger: Ledger, uow: UnitOfWork, guard: AdminGuard) -> None:
        self._ledger: Ledger = ledger
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        student_id: uuid.UUID,
        work_type_id: uuid.UUID,
        points: Decimal,
        comment: str | None,
    ) -> GradeEntry:
        """Add them.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The student.
            work_type_id: uuid.UUID - An accumulating work type.
            points: Decimal - How many.
            comment: str | None - A note for the student.

        Returns:
            GradeEntry - The entry.

        """
        self._guard.require(actor)
        async with self._uow:
            entry = await self._ledger.add_entry(
                student_id,
                work_type_id,
                points,
                comment=comment,
                graded_by=actor,
            )
            await self._uow.commit()
        return entry


@final
class StudentEntries:
    """Every entry of a student, newest first, for corrections."""

    def __init__(self, entries: EntryRepository, guard: AdminGuard) -> None:
        self._entries: EntryRepository = entries
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, student_id: uuid.UUID) -> Sequence[GradeEntry]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The student.

        Returns:
            Sequence[GradeEntry] - The entries.

        """
        self._guard.require(actor)
        return await self._entries.of_student(student_id)


@final
class EditEntry:
    """The teacher corrects an entry."""

    def __init__(self, ledger: Ledger, uow: UnitOfWork, guard: AdminGuard) -> None:
        self._ledger: Ledger = ledger
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        entry_id: uuid.UUID,
        points: Decimal,
        comment: str | None,
    ) -> GradeEntry:
        """Correct it.

        Args:
            actor: int - Teacher's Telegram id.
            entry_id: uuid.UUID - The entry.
            points: Decimal - New points.
            comment: str | None - New note.

        Returns:
            GradeEntry - The corrected entry.

        """
        self._guard.require(actor)
        async with self._uow:
            entry = await self._ledger.edit_entry(
                entry_id,
                points,
                comment=comment,
                graded_by=actor,
            )
            await self._uow.commit()
        return entry


@final
class DeleteEntry:
    """The teacher deletes an entry."""

    def __init__(self, ledger: Ledger, uow: UnitOfWork, guard: AdminGuard) -> None:
        self._ledger: Ledger = ledger
        self._uow: UnitOfWork = uow
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, entry_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            entry_id: uuid.UUID - The entry.

        """
        self._guard.require(actor)
        async with self._uow:
            await self._ledger.delete_entry(entry_id, graded_by=actor)
            await self._uow.commit()
