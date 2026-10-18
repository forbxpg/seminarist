"""Every package's MetaData, for Alembic's autogenerate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from smr.core.audit import AUDIT_METADATA
from smr.gradebook.infrastructure.models import METADATA as GRADEBOOK_METADATA
from smr.homework.infrastructure.models import METADATA as HOMEWORK_METADATA
from smr.materials.infrastructure.models import METADATA as MATERIALS_METADATA
from smr.notifications.infrastructure.models import (
    METADATA as NOTIFICATIONS_METADATA,
)
from smr.review.infrastructure.models import METADATA as REVIEW_METADATA
from smr.roster.infrastructure.models import METADATA as ROSTER_METADATA
from smr.sessions.infrastructure.models import METADATA as SESSIONS_METADATA

if TYPE_CHECKING:
    from sqlalchemy import MetaData


def all_metadata() -> list[MetaData]:
    """Collect the MetaData of every schema the migrator manages.

    Returns:
        list[MetaData] - One per package schema.

    """
    return [
        AUDIT_METADATA,
        ROSTER_METADATA,
        GRADEBOOK_METADATA,
        SESSIONS_METADATA,
        HOMEWORK_METADATA,
        NOTIFICATIONS_METADATA,
        MATERIALS_METADATA,
        REVIEW_METADATA,
    ]
