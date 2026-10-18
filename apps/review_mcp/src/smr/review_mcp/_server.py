"""The stdio server the grading agent connects to."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from mcp.server import MCPServer

from ._di import make_container
from ._rules import RULES
from ._tools import register

if TYPE_CHECKING:
    from dishka import AsyncContainer


def build_server(container: AsyncContainer) -> MCPServer:
    """Build the server with the four grading tools.

    Args:
        container: AsyncContainer - A request scope per tool call.

    Returns:
        MCPServer - Named `seminarist-review`.

    """
    server = MCPServer(
        name="seminarist-review",
        instructions=RULES,
    )
    register(server, container)
    return server


def main() -> None:
    """Serve the tools on stdio. Logs go to stderr; stdout is the protocol."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    asyncio.run(_serve())


async def _serve() -> None:
    container = make_container()
    try:
        await build_server(container).run_stdio_async()
    finally:
        await container.close()
