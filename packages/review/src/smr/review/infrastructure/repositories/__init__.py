"""The review's rows over the request's session."""

from __future__ import annotations

from ._appeals import SqlAlchemyAppeals
from ._verdicts import SqlAlchemyVerdicts

__all__ = ("SqlAlchemyAppeals", "SqlAlchemyVerdicts")
