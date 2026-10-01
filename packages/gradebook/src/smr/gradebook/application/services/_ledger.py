"""The ledger: every write of points goes through here and into the audit log."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Collection, Mapping
from datetime import datetime
from decimal import Decimal
from typing import final

from smr.core.audit import ActorKind, AuditEntry, AuditLog
from smr.core.clock import Clock
from smr.gradebook.application.ports import (
    EntryRepository,
    ItemRepository,
    WorkTypeRepository,
)
from smr.gradebook.domain import (
    EntryNotFoundError,
    GradeEntry,
    GradeItem,
    ItemNotFoundError,
    PointsOutOfRangeError,
    ScoringMode,
    WorkType,
    WorkTypeKind,
    WorkTypeNotFoundError,
)
from smr.gradebook.scoring import (
    StudentScore,
    priority_weights,
    score_student,
)
from smr.roster.application.contracts import RosterApi

_ZERO = Decimal(0)


def _entry_fields(entry: GradeEntry | None) -> dict[str, object] | None:
    if entry is None:
        return None
    return {
        "student_id": str(entry.student_id),
        "work_type_id": str(entry.work_type_id),
        "item_id": None if entry.item_id is None else str(entry.item_id),
        "points": str(entry.points),
        "excused": entry.excused,
    }


@final
class Ledger:
    """`GradebookApi`, plus what the gradebook's own use cases share.

    It never commits: it works in its caller's transaction.
    """

    def __init__(
        self,
        work_types: WorkTypeRepository,
        items: ItemRepository,
        entries: EntryRepository,
        roster: RosterApi,
        audit: AuditLog,
        clock: Clock,
    ) -> None:
        self._work_types: WorkTypeRepository = work_types
        self._items: ItemRepository = items
        self._entries: EntryRepository = entries
        self._roster: RosterApi = roster
        self._audit: AuditLog = audit
        self._clock: Clock = clock

    async def work_type(self, work_type_id: uuid.UUID) -> WorkType | None:
        """Read a work type.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            WorkType | None - It, or None.

        """
        return await self._work_types.get(work_type_id)

    async def entry(self, entry_id: uuid.UUID) -> GradeEntry | None:
        """Read an entry.

        Args:
            entry_id: uuid.UUID - It.

        Returns:
            GradeEntry | None - It, or None.

        """
        return await self._entries.get(entry_id)

    async def work_types(self, group_id: uuid.UUID) -> list[WorkType]:
        """List a group's work types in report order.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            list[WorkType] - Its work types.

        """
        return list(await self._work_types.of_group(group_id))

    async def work_type_of_kind(
        self,
        group_id: uuid.UUID,
        kind: WorkTypeKind,
    ) -> WorkType | None:
        """Find a group's first work type of a kind.

        Args:
            group_id: uuid.UUID - The group.
            kind: WorkTypeKind - The kind.

        Returns:
            WorkType | None - It, or None.

        """
        found = await self._work_types.of_kind(group_id, kind)
        return found[0] if found else None

    async def create_item(
        self,
        work_type_id: uuid.UUID,
        title: str,
        max_points: Decimal,
        counts_from: datetime,
    ) -> GradeItem:
        """Issue an item.

        Args:
            work_type_id: uuid.UUID - Its work type; it must be proportional.
            title: str - Its title.
            max_points: Decimal - The most a student may get.
            counts_from: datetime - From when it counts against everyone.

        Returns:
            GradeItem - The item.

        Raises:
            WorkTypeNotFoundError: If there is no such work type.
            ValueError: If the work type accumulates or the maximum is not positive.

        """
        work_type = await self._work_types.get(work_type_id)
        if work_type is None:
            raise WorkTypeNotFoundError
        if work_type.mode is not ScoringMode.PROPORTIONAL:
            msg = "items are issued only for a proportional work type"
            raise ValueError(msg)
        _positive(max_points)
        item = GradeItem(uuid.uuid4(), work_type_id, title, max_points, counts_from)
        await self._items.add(item)
        return item

    async def update_item(
        self,
        item_id: uuid.UUID,
        *,
        title: str,
        max_points: Decimal,
        counts_from: datetime,
    ) -> GradeItem:
        """Change an item.

        Args:
            item_id: uuid.UUID - It.
            title: str - Its title.
            max_points: Decimal - The most a student may get.
            counts_from: datetime - From when it counts.

        Returns:
            GradeItem - The changed item.

        Raises:
            ItemNotFoundError: If there is no such item.
            PointsOutOfRangeError: If someone already has more than the new maximum.

        """
        item = await self._items.get(item_id)
        if item is None:
            raise ItemNotFoundError
        _positive(max_points)
        if any(
            entry.points > max_points for entry in await self._entries.of_item(item_id)
        ):
            raise PointsOutOfRangeError
        changed = dataclasses.replace(
            item,
            title=title,
            max_points=max_points,
            counts_from=counts_from,
        )
        await self._items.update(changed)
        return changed

    async def delete_item(self, item_id: uuid.UUID) -> None:
        """Withdraw an item with its points.

        Args:
            item_id: uuid.UUID - It.

        """
        await self._items.delete(item_id)

    async def set_entry(
        self,
        student_id: uuid.UUID,
        item_id: uuid.UUID,
        points: Decimal,
        *,
        excused: bool,
        comment: str | None,
        graded_by: int | None,
    ) -> GradeEntry:
        """Give a student points for an item, replacing what they had.

        Args:
            student_id: uuid.UUID - The student.
            item_id: uuid.UUID - The item.
            points: Decimal - From 0 to the item's maximum; 0 when excused.
            excused: bool - The item does not count for this student.
            comment: str | None - The teacher's note.
            graded_by: int | None - Teacher's Telegram id; none for the system.

        Returns:
            GradeEntry - The entry.

        Raises:
            ItemNotFoundError: If there is no such item.
            PointsOutOfRangeError: If the points are outside the item's range.

        """
        item = await self._items.get(item_id)
        if item is None:
            raise ItemNotFoundError
        if excused:
            points = _ZERO
        if not _ZERO <= points <= item.max_points:
            raise PointsOutOfRangeError
        before = await self._entries.for_item(student_id, item_id)
        entry = GradeEntry(
            entry_id=uuid.uuid4() if before is None else before.entry_id,
            student_id=student_id,
            work_type_id=item.work_type_id,
            item_id=item_id,
            points=points,
            excused=excused,
            comment=comment,
            graded_by=graded_by,
            graded_at=self._clock.now(),
        )
        if before is None:
            await self._entries.add(entry)
        else:
            await self._entries.update(entry)
        await self._record(graded_by, "grade.set", entry.entry_id, before, entry)
        return entry

    async def clear_entry(
        self,
        student_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        graded_by: int | None,
    ) -> None:
        """Take back a student's points for an item.

        Args:
            student_id: uuid.UUID - The student.
            item_id: uuid.UUID - The item.
            graded_by: int | None - Teacher's Telegram id; none for the system.

        """
        before = await self._entries.for_item(student_id, item_id)
        if before is None:
            return
        await self._entries.delete(before.entry_id)
        await self._record(graded_by, "grade.cleared", before.entry_id, before, None)

    async def add_entry(
        self,
        student_id: uuid.UUID,
        work_type_id: uuid.UUID,
        points: Decimal,
        *,
        comment: str | None,
        graded_by: int | None,
    ) -> GradeEntry:
        """Add accumulating points.

        Args:
            student_id: uuid.UUID - The student.
            work_type_id: uuid.UUID - An accumulating work type.
            points: Decimal - From 0 to the cap.
            comment: str | None - The teacher's note.
            graded_by: int | None - Teacher's Telegram id.

        Returns:
            GradeEntry - The entry.

        Raises:
            WorkTypeNotFoundError: If there is no such work type.
            ValueError: If the work type is proportional.
            PointsOutOfRangeError: If the points are outside 0 to the cap.

        """
        work_type = await self._work_types.get(work_type_id)
        if work_type is None:
            raise WorkTypeNotFoundError
        if work_type.mode is not ScoringMode.ACCUMULATING:
            msg = "loose points go only to an accumulating work type"
            raise ValueError(msg)
        if not _ZERO <= points <= work_type.cap:
            raise PointsOutOfRangeError
        entry = GradeEntry(
            entry_id=uuid.uuid4(),
            student_id=student_id,
            work_type_id=work_type_id,
            item_id=None,
            points=points,
            excused=False,
            comment=comment,
            graded_by=graded_by,
            graded_at=self._clock.now(),
        )
        await self._entries.add(entry)
        await self._record(graded_by, "grade.added", entry.entry_id, None, entry)
        return entry

    async def edit_entry(
        self,
        entry_id: uuid.UUID,
        points: Decimal,
        *,
        comment: str | None,
        graded_by: int,
    ) -> GradeEntry:
        """Change the points of an entry.

        Args:
            entry_id: uuid.UUID - It.
            points: Decimal - New points.
            comment: str | None - New note.
            graded_by: int - Teacher's Telegram id.

        Returns:
            GradeEntry - The changed entry.

        Raises:
            EntryNotFoundError: If there is no such entry.
            PointsOutOfRangeError: If the points are out of range.

        """
        before = await self._entries.get(entry_id)
        if before is None:
            raise EntryNotFoundError
        limit = await self._limit(before)
        if not _ZERO <= points <= limit:
            raise PointsOutOfRangeError
        entry = dataclasses.replace(
            before,
            points=points,
            excused=False,
            comment=comment,
            graded_by=graded_by,
            graded_at=self._clock.now(),
        )
        await self._entries.update(entry)
        await self._record(graded_by, "grade.edited", entry_id, before, entry)
        return entry

    async def delete_entry(self, entry_id: uuid.UUID, *, graded_by: int | None) -> None:
        """Delete an entry.

        Args:
            entry_id: uuid.UUID - It.
            graded_by: int | None - Teacher's Telegram id.

        Raises:
            EntryNotFoundError: If there is no such entry.

        """
        before = await self._entries.get(entry_id)
        if before is None:
            raise EntryNotFoundError
        await self._entries.delete(entry_id)
        await self._record(graded_by, "grade.deleted", entry_id, before, None)

    async def scores(self, group_id: uuid.UUID) -> dict[uuid.UUID, StudentScore]:
        """Score every student of a group's roster.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            dict[uuid.UUID, StudentScore] - Each student's score, in roster order.

        """
        work_types = await self._work_types.of_group(group_id)
        items = await self._items.of_group(group_id)
        entries = await self._entries.of_group(group_id)
        now = self._clock.now()
        by_student: dict[uuid.UUID, list[GradeEntry]] = {}
        for entry in entries:
            by_student.setdefault(entry.student_id, []).append(entry)
        return {
            student.student_id: score_student(
                student.student_id,
                work_types,
                items,
                by_student.get(student.student_id, []),
                now,
            )
            for student in await self._roster.students_of(group_id)
        }

    async def priority_weights(
        self,
        group_id: uuid.UUID,
        board_calls: Mapping[uuid.UUID, int],
        candidates: Collection[uuid.UUID],
    ) -> dict[uuid.UUID, float]:
        """Weigh the candidates for the board.

        Args:
            group_id: uuid.UUID - The group.
            board_calls: Mapping[uuid.UUID, int] - Every student's calls this semester.
            candidates: Collection[uuid.UUID] - Who may be called now.

        Returns:
            dict[uuid.UUID, float] - Each candidate's probability.

        Raises:
            ValueError: If the group is unknown.

        """
        group = await self._roster.group(group_id)
        if group is None:
            msg = "unknown group"
            raise ValueError(msg)
        scores = await self.scores(group_id)
        population = {
            student: (board_calls.get(student, 0), score.priority_share)
            for student, score in scores.items()
        }
        return priority_weights(
            population,
            candidates,
            board_weight=group.settings.board_weight,
            score_weight=group.settings.score_weight,
        )

    async def _limit(self, entry: GradeEntry) -> Decimal:
        if entry.item_id is not None:
            item = await self._items.get(entry.item_id)
            return _ZERO if item is None else item.max_points
        work_type = await self._work_types.get(entry.work_type_id)
        return _ZERO if work_type is None else work_type.cap

    async def _record(
        self,
        graded_by: int | None,
        action: str,
        entry_id: uuid.UUID,
        before: GradeEntry | None,
        after: GradeEntry | None,
    ) -> None:
        await self._audit.record(
            AuditEntry(
                actor_kind=ActorKind.SYSTEM if graded_by is None else ActorKind.ADMIN,
                actor_id=None if graded_by is None else str(graded_by),
                action=action,
                entity="grade_entry",
                entity_id=str(entry_id),
                before=_entry_fields(before),
                after=_entry_fields(after),
            ),
        )


def _positive(max_points: Decimal) -> None:
    if max_points <= _ZERO:
        msg = "the maximum is positive"
        raise ValueError(msg)
