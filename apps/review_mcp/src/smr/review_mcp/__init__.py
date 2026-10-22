"""smr-review-mcp: the grading agent's tools."""

from __future__ import annotations

from ._di import make_container
from ._server import build_server, main
from ._session import session_main

__all__ = ("build_server", "main", "make_container", "session_main")
