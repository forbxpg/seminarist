"""The teacher's assignments: set, change, copy, delete, list."""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from smr.core.audit import ActorKind, AuditEntry
from smr.core.files import FileKind
from smr.gradebook.domain import WorkTypeKind, WorkTypeNotFoundError
from smr.homework.domain import (
    Assignment,
    StatementFile,
    Submission,
    SubmissionStatus,
)

from ._common import assignment_of, open_group
from ._upload import Upload

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

    from smr.core.access import AdminGuard
    from smr.core.audit import AuditLog
    from smr.core.clock import Clock
    from smr.core.database import UnitOfWork
    from smr.core.files import FileStore
    from smr.gradebook.application.contracts import GradebookApi
    from smr.homework.application.ports import (
        AssignmentRepository,
        FileRepository,
        SubmissionRepository,
    )
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Student


ALL_KINDS: frozenset[FileKind] = frozenset(FileKind)


@dataclass(frozen=True, slots=True)
class AssignmentDraft:
    """What the teacher fills in for an assignment.

    Attributes:
        title: str - Its title.
        body: str - The statement as text.
        deadline: datetime - When it is due.
        max_points: Decimal - The most a student may get.

    """

    title: str
    body: str
    deadline: datetime
    max_points: Decimal


@dataclass(frozen=True, slots=True)
class AssignmentSummary:
    """An assignment with how far the group is.

    Attributes:
        assignment: Assignment - The assignment.
        submitted: int - Students with a live version.
        graded: int - Of them, graded.
        late: int - Of them, sent late.

    """

    assignment: Assignment
    submitted: int
    graded: int
    late: int


def _audit(actor: int, action: str, assignment_id: uuid.UUID) -> AuditEntry:
    return AuditEntry(
        ActorKind.ADMIN,
        str(actor),
        action,
        "assignment",
        str(assignment_id),
    )


def _clean(draft: AssignmentDraft) -> AssignmentDraft:
    title = " ".join(draft.title.split())
    if not title:
        msg = "an assignment has a title"
        raise ValueError(msg)
    return dataclasses.replace(draft, title=title, body=draft.body.strip())


@final
class CreateAssignment:
    """A new assignment, issued in the ledger with its deadline."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        files: FileStore,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
        clock: Clock,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard
        self._clock: Clock = clock

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
        draft: AssignmentDraft,
        *,
        statement: Upload | None = None,
        work_type_id: uuid.UUID | None = None,
    ) -> Assignment:
        """Set it.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.
            draft: AssignmentDraft - Its fields.
            statement: Upload | None - The statement as a file.
            work_type_id: uuid.UUID | None - The work type; the group's homework one
                when none.

        Returns:
            Assignment - The assignment.

        Raises:
            WorkTypeNotFoundError: If the group has no such work type.

        """
        self._guard.require(actor)
        clean = _clean(draft)
        async with self._uow:
            _ = await open_group(self._roster, group_id)
            work_type = (
                await self._gradebook.work_type_of_kind(group_id, WorkTypeKind.HOMEWORK)
                if work_type_id is None
                else await self._gradebook.work_type(work_type_id)
            )
            if work_type is None or work_type.group_id != group_id:
                raise WorkTypeNotFoundError
            item = await self._gradebook.create_item(
                work_type.work_type_id,
                clean.title,
                clean.max_points,
                clean.deadline,
            )
            stored = None
            if statement is not None:
                saved = await self._files.save(
                    statement.data,
                    accepted=ALL_KINDS,
                    now=self._clock.now(),
                )
                stored = StatementFile(
                    statement.tg_file_id,
                    saved.relative_path,
                    saved.kind,
                )
            assignment = Assignment(
                assignment_id=uuid.uuid4(),
                group_id=group_id,
                work_type_id=work_type.work_type_id,
                item_id=item.item_id,
                title=clean.title,
                body=clean.body,
                statement=stored,
                deadline=clean.deadline,
                max_points=clean.max_points,
            )
            await self._assignments.add(assignment)
            await self._audit.record(
                _audit(actor, "assignment.created", assignment.assignment_id),
            )
            await self._uow.commit()
        return assignment


@final
class UpdateAssignment:
    """New title, text, deadline or maximum; the ledger item follows."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        roster: RosterApi,
        gradebook: GradebookApi,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._roster: RosterApi = roster
        self._gradebook: GradebookApi = gradebook
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        assignment_id: uuid.UUID,
        draft: AssignmentDraft,
    ) -> Assignment:
        """Change it.

        Args:
            actor: int - Teacher's Telegram id.
            assignment_id: uuid.UUID - It.
            draft: AssignmentDraft - Its new fields.

        Returns:
            Assignment - The changed assignment.

        """
        self._guard.require(actor)
        clean = _clean(draft)
        async with self._uow:
            before = await assignment_of(self._assignments, assignment_id)
            _ = await open_group(self._roster, before.group_id)
            after = dataclasses.replace(
                before,
                title=clean.title,
                body=clean.body,
                deadline=clean.deadline,
                max_points=clean.max_points,
            )
            if before.item_id is not None:
                _ = await self._gradebook.update_item(
                    before.item_id,
                    title=clean.title,
                    max_points=clean.max_points,
                    counts_from=clean.deadline,
                )
            await self._assignments.update(after)
            await self._audit.record(
                AuditEntry(
                    ActorKind.ADMIN,
                    str(actor),
                    "assignment.changed",
                    "assignment",
                    str(assignment_id),
                    before={
                        "deadline": before.deadline.isoformat(),
                        "max_points": str(before.max_points),
                    },
                    after={
                        "deadline": after.deadline.isoformat(),
                        "max_points": str(after.max_points),
                    },
                ),
            )
            await self._uow.commit()
        return after


@final
class CopyAssignment:
    """The same assignment for another group, with its own deadline."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        files: FileStore,
        create: CreateAssignment,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._files: FileStore = files
        self._create: CreateAssignment = create
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        assignment_id: uuid.UUID,
        group_id: uuid.UUID,
        deadline: datetime,
    ) -> Assignment:
        """Copy it.

        Args:
            actor: int - Teacher's Telegram id.
            assignment_id: uuid.UUID - The original.
            group_id: uuid.UUID - The other group.
            deadline: datetime - The copy's deadline.

        Returns:
            Assignment - The copy.

        """
        self._guard.require(actor)
        source = await assignment_of(self._assignments, assignment_id)
        statement = None
        if source.statement is not None:
            path = self._files.path(source.statement.path)
            data = await asyncio.to_thread(path.read_bytes)
            statement = Upload(
                data,
                source.statement.tg_file_id,
                source.statement.tg_file_id,
                deadline,
            )
        return await self._create(
            actor,
            group_id,
            AssignmentDraft(source.title, source.body, deadline, source.max_points),
            statement=statement,
        )


@final
class DeleteAssignment:
    """An assignment deleted with every submission, file and point of it."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        stored: FileRepository,
        gradebook: GradebookApi,
        files: FileStore,
        uow: UnitOfWork,
        audit: AuditLog,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._stored: FileRepository = stored
        self._gradebook: GradebookApi = gradebook
        self._files: FileStore = files
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int, assignment_id: uuid.UUID) -> None:
        """Delete it.

        Args:
            actor: int - Teacher's Telegram id.
            assignment_id: uuid.UUID - It.

        """
        self._guard.require(actor)
        async with self._uow:
            assignment = await assignment_of(self._assignments, assignment_id)
            paths = list(await self._stored.paths_of_assignment(assignment_id))
            if assignment.item_id is not None:
                await self._gradebook.delete_item(assignment.item_id)
            await self._assignments.delete(assignment_id)
            await self._audit.record(_audit(actor, "assignment.deleted", assignment_id))
            await self._uow.commit()
        for path in paths:
            await self._files.delete(path)


@final
class ListAssignments:
    """A group's assignments with how many submitted, were graded, were late."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        group_id: uuid.UUID,
    ) -> list[AssignmentSummary]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            group_id: uuid.UUID - The group.

        Returns:
            list[AssignmentSummary] - The latest deadline first.

        """
        self._guard.require(actor)
        result: list[AssignmentSummary] = []
        for assignment in await self._assignments.of_group(group_id):
            live = await self._submissions.live_of_assignment(assignment.assignment_id)
            result.append(
                AssignmentSummary(
                    assignment=assignment,
                    submitted=len(live),
                    graded=sum(1 for s in live if s.status is SubmissionStatus.GRADED),
                    late=sum(1 for s in live if s.is_late),
                ),
            )
        return result


@final
class AssignmentRoster:
    """Each student of the group next to their live version, for the teacher."""

    def __init__(
        self,
        assignments: AssignmentRepository,
        submissions: SubmissionRepository,
        roster: RosterApi,
        guard: AdminGuard,
    ) -> None:
        self._assignments: AssignmentRepository = assignments
        self._submissions: SubmissionRepository = submissions
        self._roster: RosterApi = roster
        self._guard: AdminGuard = guard

    async def __call__(
        self,
        actor: int,
        assignment_id: uuid.UUID,
    ) -> list[tuple[Student, Submission | None]]:
        """List them.

        Args:
            actor: int - Teacher's Telegram id.
            assignment_id: uuid.UUID - The assignment.

        Returns:
            list[tuple[Student, Submission | None]] - In roster order.

        """
        self._guard.require(actor)
        assignment = await assignment_of(self._assignments, assignment_id)
        live = {
            s.student_id: s
            for s in await self._submissions.live_of_assignment(assignment_id)
        }
        return [
            (student, live.get(student.student_id))
            for student in await self._roster.students_of(assignment.group_id)
        ]
