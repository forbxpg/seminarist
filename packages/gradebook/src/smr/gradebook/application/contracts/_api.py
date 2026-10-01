"""The ledger as sessions and homework use it, in their own transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Collection, Mapping
    from datetime import datetime
    from decimal import Decimal

    from smr.gradebook.domain import GradeEntry, GradeItem, WorkType, WorkTypeKind


class GradebookApi(Protocol):
    """Write points and read the board priority from another package."""

    async def work_type(self, work_type_id: uuid.UUID) -> WorkType | None:
        """Read a work type.

        Args:
            work_type_id: uuid.UUID - It.

        Returns:
            WorkType | None - It, or None.

        """
        ...

    async def work_types(self, group_id: uuid.UUID) -> list[WorkType]:
        """List a group's work types in report order.

        Args:
            group_id: uuid.UUID - The group.

        Returns:
            list[WorkType] - Its work types.

        """
        ...

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
            WorkType | None - It, or None when the group has none.

        """
        ...

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

        """
        ...

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

        """
        ...

    async def delete_item(self, item_id: uuid.UUID) -> None:
        """Withdraw an item with its points.

        Args:
            item_id: uuid.UUID - It.

        """
        ...

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

        """
        ...

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
        ...

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

        """
        ...

    async def delete_entry(self, entry_id: uuid.UUID, *, graded_by: int | None) -> None:
        """Delete an entry.

        Args:
            entry_id: uuid.UUID - It.
            graded_by: int | None - Teacher's Telegram id.

        """
        ...

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

        """
        ...
