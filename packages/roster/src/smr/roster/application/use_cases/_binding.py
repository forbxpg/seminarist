"""A Telegram account and its roster row: claim, teacher's decision, unbind, forget."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Sequence
from typing import final

from smr.core.access import AdminGuard
from smr.core.audit import AuditLog
from smr.core.clock import Clock
from smr.core.database import UnitOfWork
from smr.roster.application.ports import GroupRepository, StudentRepository
from smr.roster.domain import (
    CONSENT_VERSION,
    AlreadyBoundError,
    BindingStatus,
    Group,
    GroupArchivedError,
    InviteNotFoundError,
    NameTakenError,
    NotPendingError,
    Student,
    StudentNotFoundError,
)

from ._audit import by_admin, by_student
from ._results import Membership


async def _open_group(groups: GroupRepository, invite_code: str) -> Group:
    group = await groups.by_invite(invite_code)
    if group is None:
        raise InviteNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group


@final
class ResolveInvite:
    """The group a join link leads to."""

    def __init__(self, groups: GroupRepository) -> None:
        self._groups: GroupRepository = groups

    async def __call__(self, invite_code: str) -> Group:
        """Find it.

        Args:
            invite_code: str - Payload of the link.

        Returns:
            Group - The active group; an unknown or archived one is an error.

        """
        return await _open_group(self._groups, invite_code)


@final
class ClaimableNames:
    """The names of a group nobody has claimed yet."""

    def __init__(self, groups: GroupRepository, students: StudentRepository) -> None:
        self._groups: GroupRepository = groups
        self._students: StudentRepository = students

    async def __call__(self, invite_code: str) -> Sequence[Student]:
        """List them.

        Args:
            invite_code: str - Payload of the group's link.

        Returns:
            Sequence[Student] - Unbound rows by name.

        """
        group = await _open_group(self._groups, invite_code)
        roster = await self._students.of_group(group.group_id)
        return [row for row in roster if row.binding is BindingStatus.UNBOUND]


@final
class ClaimStudent:
    """An account claims a name; it waits for the teacher, seeing nothing yet."""

    def __init__(
        self,
        groups: GroupRepository,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        clock: Clock,
    ) -> None:
        self._groups: GroupRepository = groups
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._clock: Clock = clock

    async def __call__(
        self,
        invite_code: str,
        student_id: uuid.UUID,
        tg_user_id: int,
        consent_version: str,
    ) -> Membership:
        """Claim it.

        Args:
            invite_code: str - Payload of the group's link.
            student_id: uuid.UUID - The chosen row.
            tg_user_id: int - The claiming account.
            consent_version: str - The privacy notice it accepted.

        Returns:
            Membership - The group and the pending row, to tell the teacher.

        Raises:
            StudentNotFoundError: If the row is not of this group.
            AlreadyBoundError: If the account already holds a row of the group.
            NameTakenError: If someone has claimed the row first.

        """
        now = self._clock.now()
        async with self._uow:
            group = await _open_group(self._groups, invite_code)
            student = await self._students.get(student_id)
            if student is None or student.group_id != group.group_id:
                raise StudentNotFoundError
            mine = await self._students.of_account(tg_user_id)
            if any(row.group_id == group.group_id for row in mine):
                raise AlreadyBoundError
            if not await self._students.claim(
                student_id,
                tg_user_id,
                consent_version,
                now,
            ):
                raise NameTakenError
            await self._audit.record(
                by_student(
                    student_id,
                    "binding.requested",
                    after={"consent_version": consent_version},
                ),
            )
            await self._uow.commit()
        claimed = dataclasses.replace(
            student,
            tg_user_id=tg_user_id,
            binding=BindingStatus.PENDING,
            binding_requested_at=now,
            consent_version=consent_version,
            consent_at=now,
        )
        return Membership(group=group, student=claimed)


@final
class PendingBindings:
    """Claims waiting for the teacher."""

    def __init__(
        self,
        groups: GroupRepository,
        students: StudentRepository,
        guard: AdminGuard,
    ) -> None:
        self._groups: GroupRepository = groups
        self._students: StudentRepository = students
        self._guard: AdminGuard = guard

    async def __call__(self, actor: int) -> Sequence[Membership]:
        """List them, oldest first.

        Args:
            actor: int - Teacher's Telegram id.

        Returns:
            Sequence[Membership] - The claims with their groups.

        """
        self._guard.require(actor)
        result: list[Membership] = []
        for student in await self._students.pending():
            group = await self._groups.get(student.group_id)
            if group is not None:
                result.append(Membership(group=group, student=student))
        return result


async def _row(students: StudentRepository, student_id: uuid.UUID) -> Student:
    student = await students.get(student_id)
    if student is None:
        raise StudentNotFoundError
    return student


@final
class ApproveBinding:
    """The teacher confirms the claim: the student gets access."""

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
        """Approve it.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The pending row.

        Returns:
            Student - The bound row.

        Raises:
            NotPendingError: If the row is not waiting.

        """
        self._guard.require(actor)
        async with self._uow:
            student = await _row(self._students, student_id)
            if student.binding is not BindingStatus.PENDING:
                raise NotPendingError
            await self._students.set_binding(student_id, BindingStatus.BOUND)
            await self._audit.record(
                by_admin(actor, "binding.approved", "student", student_id),
            )
            await self._uow.commit()
        return dataclasses.replace(student, binding=BindingStatus.BOUND)


@final
class RejectBinding:
    """The teacher refuses the claim: the name is free again."""

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
        """Reject it.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The pending row.

        Returns:
            Student - The row as it was, with the account to tell.

        Raises:
            NotPendingError: If the row is not waiting.

        """
        self._guard.require(actor)
        async with self._uow:
            student = await _row(self._students, student_id)
            if student.binding is not BindingStatus.PENDING:
                raise NotPendingError
            await self._students.release(student_id)
            await self._audit.record(
                by_admin(actor, "binding.rejected", "student", student_id),
            )
            await self._uow.commit()
        return student


@final
class Unbind:
    """The teacher detaches an account from a row."""

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
        """Unbind it.

        Args:
            actor: int - Teacher's Telegram id.
            student_id: uuid.UUID - The row.

        Returns:
            Student - The row as it was, with the account to tell.

        """
        self._guard.require(actor)
        async with self._uow:
            student = await _row(self._students, student_id)
            if student.binding is BindingStatus.UNBOUND:
                return student
            await self._students.release(student_id)
            await self._audit.record(
                by_admin(actor, "binding.unbound", "student", student_id),
            )
            await self._uow.commit()
        return student


@final
class Memberships:
    """The rows an account claims or holds, with their active groups."""

    def __init__(self, groups: GroupRepository, students: StudentRepository) -> None:
        self._groups: GroupRepository = groups
        self._students: StudentRepository = students

    async def __call__(self, tg_user_id: int) -> Sequence[Membership]:
        """List them.

        Args:
            tg_user_id: int - Telegram user id.

        Returns:
            Sequence[Membership] - Rows in active groups, pending ones included.

        """
        result: list[Membership] = []
        for student in await self._students.of_account(tg_user_id):
            group = await self._groups.get(student.group_id)
            if group is not None and group.is_active:
                result.append(Membership(group=group, student=student))
        return result


@final
class AcceptConsent:
    """A student accepts the current privacy notice on every bound row."""

    def __init__(
        self,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
        clock: Clock,
    ) -> None:
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._clock: Clock = clock

    async def __call__(self, tg_user_id: int) -> int:
        """Record the acceptance.

        Args:
            tg_user_id: int - The account.

        Returns:
            int - How many bound rows were updated.

        """
        now = self._clock.now()
        async with self._uow:
            bound = [
                row
                for row in await self._students.of_account(tg_user_id)
                if row.binding is BindingStatus.BOUND
            ]
            updated = await self._students.set_consent(tg_user_id, CONSENT_VERSION, now)
            for row in bound:
                await self._audit.record(
                    by_student(
                        row.student_id,
                        "roster.consent",
                        after={"version": CONSENT_VERSION},
                    ),
                )
            await self._uow.commit()
        return updated


@final
class ForgetAccount:
    """A student asks to be forgotten: every row of the account is unbound."""

    def __init__(
        self,
        students: StudentRepository,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> None:
        self._students: StudentRepository = students
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(self, tg_user_id: int) -> Sequence[Student]:
        """Unbind every row.

        Args:
            tg_user_id: int - Telegram user id.

        Returns:
            Sequence[Student] - The rows it held, so their files can go too.

        """
        async with self._uow:
            rows = await self._students.of_account(tg_user_id)
            for row in rows:
                await self._students.release(row.student_id)
                await self._audit.record(
                    by_student(row.student_id, "binding.forgotten"),
                )
            await self._uow.commit()
        return rows
