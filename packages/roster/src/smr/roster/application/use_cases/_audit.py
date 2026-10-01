"""Audit entries of the roster: ids and states, never names."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from smr.core.audit import ActorKind, AuditEntry


def by_admin(
    actor: int,
    action: str,
    entity: str,
    entity_id: uuid.UUID,
    *,
    before: Mapping[str, object] | None = None,
    after: Mapping[str, object] | None = None,
) -> AuditEntry:
    """Describe a teacher's change.

    Args:
        actor: int - Teacher's Telegram id.
        action: str - What happened.
        entity: str - Kind of the changed thing.
        entity_id: uuid.UUID - Its id.
        before: Mapping[str, object] | None - Fields before.
        after: Mapping[str, object] | None - Fields after.

    Returns:
        AuditEntry - The entry.

    """
    return AuditEntry(
        actor_kind=ActorKind.ADMIN,
        actor_id=str(actor),
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        before=before,
        after=after,
    )


def by_student(
    student_id: uuid.UUID,
    action: str,
    *,
    after: Mapping[str, object] | None = None,
) -> AuditEntry:
    """Describe a student's change of their own roster row.

    Args:
        student_id: uuid.UUID - The row, which is also the actor.
        action: str - What happened.
        after: Mapping[str, object] | None - Fields after.

    Returns:
        AuditEntry - The entry.

    """
    return AuditEntry(
        actor_kind=ActorKind.STUDENT,
        actor_id=str(student_id),
        action=action,
        entity="student",
        entity_id=str(student_id),
        after=after,
    )


def by_system(
    action: str,
    entity: str,
    entity_id: uuid.UUID,
) -> AuditEntry:
    """Describe a change the system made by itself.

    Args:
        action: str - What happened.
        entity: str - Kind of the changed thing.
        entity_id: uuid.UUID - Its id.

    Returns:
        AuditEntry - The entry.

    """
    return AuditEntry(
        actor_kind=ActorKind.SYSTEM,
        actor_id=None,
        action=action,
        entity=entity,
        entity_id=str(entity_id),
    )
