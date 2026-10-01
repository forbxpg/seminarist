"""What a notice is and how it reads."""

from __future__ import annotations

from ._kinds import NotificationKind
from ._notice import Notice
from ._texts import render

__all__ = ("Notice", "NotificationKind", "render")
