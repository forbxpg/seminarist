"""smr-review-mcp: the grading agent's tools."""

from __future__ import annotations

from ._di import make_container
from ._server import build_server, main

__all__ = ("build_server", "main", "make_container")
