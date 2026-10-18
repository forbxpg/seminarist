"""An audit entry: general, with no knowledge of the domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class ActorKind(StrEnum):
    """Who acted."""

    ADMIN = "admin"
    STUDENT = "student"
    SYSTEM = "system"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One change worth remembering.

    Names never go in: the log outlives the roster, and an id without its roster row
    tells nothing about a person.

    Attributes:
        actor_kind: ActorKind - Who acted.
        actor_id: str | None - Teacher's Telegram id, student's roster id, or the
            agent's model name; none for the system.
        action: str - What happened, a label its domain defines.
        entity: str - Kind of the changed thing, e.g. `"grade_entry"`.
        entity_id: str - Its id.
        before: Mapping[str, object] | None - Its fields before; none on creation.
        after: Mapping[str, object] | None - Its fields after; none on deletion.

    """

    actor_kind: ActorKind
    actor_id: str | None
    action: str
    entity: str
    entity_id: str
    before: Mapping[str, object] | None = None
    after: Mapping[str, object] | None = field(default=None)
