"""Where groups and rosters are kept."""

from __future__ import annotations

from ._groups import GroupRepository
from ._students import StudentRepository

__all__ = ("GroupRepository", "StudentRepository")
