"""What homework's use cases share."""

from __future__ import annotations

from typing import TYPE_CHECKING

from smr.homework.domain import AssignmentNotFoundError, NotYourAssignmentError
from smr.roster.domain import GroupArchivedError, GroupNotFoundError

if TYPE_CHECKING:
    import uuid

    from smr.homework.application.ports import AssignmentRepository
    from smr.homework.domain import Assignment
    from smr.roster.application.contracts import RosterApi
    from smr.roster.domain import Group, Student


async def open_group(roster: RosterApi, group_id: uuid.UUID) -> Group:
    """Read a group that still takes changes.

    Args:
        roster: RosterApi - The roster.
        group_id: uuid.UUID - The group.

    Returns:
        Group - The active group.

    Raises:
        GroupNotFoundError: If there is no such group.
        GroupArchivedError: If the group is archived.

    """
    group = await roster.group(group_id)
    if group is None:
        raise GroupNotFoundError
    if not group.is_active:
        raise GroupArchivedError
    return group


async def assignment_of(
    assignments: AssignmentRepository,
    assignment_id: uuid.UUID,
) -> Assignment:
    """Read an assignment that exists.

    Args:
        assignments: AssignmentRepository - The assignments.
        assignment_id: uuid.UUID - It.

    Returns:
        Assignment - It.

    Raises:
        AssignmentNotFoundError: If there is no such assignment.

    """
    assignment = await assignments.get(assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError
    return assignment


async def student_of(
    roster: RosterApi,
    tg_user_id: int,
    assignment: Assignment,
) -> Student:
    """Find the asking account's approved row in the assignment's group.

    Args:
        roster: RosterApi - The roster.
        tg_user_id: int - The asking account.
        assignment: Assignment - The assignment.

    Returns:
        Student - The row.

    Raises:
        NotYourAssignmentError: If the account holds no approved row of that group.

    """
    student = await roster.bound_student(tg_user_id, assignment.group_id)
    if student is None:
        raise NotYourAssignmentError
    return student
