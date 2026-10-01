"""What a notice is about."""

from __future__ import annotations

from enum import StrEnum


class NotificationKind(StrEnum):
    """Kinds of notice."""

    ASSIGNMENT_PUBLISHED = "assignment_published"
    MATERIAL_PUBLISHED = "material_published"
    HOMEWORK_GRADED = "homework_graded"
    DEADLINE_REMINDER = "deadline_reminder"
    BINDING_REQUESTED = "binding_requested"
    BINDING_APPROVED = "binding_approved"
    BINDING_REJECTED = "binding_rejected"
