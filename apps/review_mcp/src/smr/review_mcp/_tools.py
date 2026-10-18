"""The four tools: the queue, the pages, and the verdict."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.utilities.types import Image
from mcp.types import TextContent

from smr.core.files import FileStore, PdfBrokenError, PdfLockedError
from smr.core.files.pdf import render_pages
from smr.review.application.use_cases import (
    PendingWorks,
    SubmitVerdict,
    TaskInput,
    TaskSheetFor,
    VerdictInput,
    WorkFile,
)
from smr.review.domain import ReviewError

from ._schemas import (
    PendingWorkOut,
    PendingWorksOut,
    VerdictIn,
    VerdictOutcomeOut,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from dishka import AsyncContainer
    from mcp.server import MCPServer

_REFUSED = (ReviewError, ValueError, PdfBrokenError, PdfLockedError)
_CENT = Decimal("0.01")


def register(server: MCPServer, container: AsyncContainer) -> None:
    """Register the grading tools on the server.

    Args:
        server: MCPServer - The server.
        container: AsyncContainer - Where the use cases come from.

    """

    @server.tool()
    async def pending_works() -> PendingWorksOut:
        """List live works that have no current verdict.

        Returns:
            PendingWorksOut - Oldest first.

        """
        return await _call(container, _pending)

    @server.tool(structured_output=False)
    async def get_task_sheet(
        task_key: str,
        part: Literal["statement", "solutions"],
        start: int = 1,
        count: int = 6,
    ) -> list[TextContent | Image]:
        """Render pages of the statement or the solutions.

        Args:
            task_key: str - `bdz:<assignment id>`.
            part: Literal["statement", "solutions"] - Which PDF.
            start: int - The first page, from 1.
            count: int - How many pages, from 1 to 6.

        Returns:
            list[TextContent | Image] - A short text, then one JPEG per page.

        """
        return await _call(
            container,
            lambda request: _sheet(request, task_key, part, start, count),
        )

    @server.tool(structured_output=False)
    async def get_work_pages(
        work_ref: str,
        start: int = 1,
        count: int = 6,
    ) -> list[TextContent | Image]:
        """Render pages of a student's PDF.

        Args:
            work_ref: str - `bdz:<version id>`.
            start: int - The first page, from 1.
            count: int - How many pages, from 1 to 6.

        Returns:
            list[TextContent | Image] - A short text, then one JPEG per page.

        """
        return await _call(
            container,
            lambda request: _pages(request, work_ref, start, count),
        )

    @server.tool()
    async def submit_verdict(verdict: VerdictIn) -> VerdictOutcomeOut:
        """Store a verdict for one live version.

        Args:
            verdict: VerdictIn - The scores and the explanations.

        Returns:
            VerdictOutcomeOut - `published` or `manual`, and the totals.

        """
        return await _call(container, lambda request: _submit(request, verdict))


async def _call[T](
    container: AsyncContainer,
    action: Callable[[AsyncContainer], Awaitable[T]],
) -> T:
    try:
        async with container() as request:
            return await action(request)
    except _REFUSED as error:
        reason = str(error)
        raise ToolError(reason) from error


async def _pending(request: AsyncContainer) -> PendingWorksOut:
    found = await (await request.get(PendingWorks))()
    return PendingWorksOut(
        works=[
            PendingWorkOut(
                work_ref=work.work_ref,
                task_key=work.task_key,
                title=work.title,
                version=work.version,
                pages=work.pages,
                sha256=work.sha256,
                is_late=work.is_late,
            )
            for work in found
        ],
    )


async def _sheet(
    request: AsyncContainer,
    task_key: str,
    part: Literal["statement", "solutions"],
    start: int,
    count: int,
) -> list[TextContent | Image]:
    sheet = await (await request.get(TaskSheetFor))(task_key)
    if part == "statement":
        relative, total = sheet.statement_path, sheet.statement_pages
    else:
        relative, total = sheet.solutions_path, sheet.solutions_pages
    scheme = [
        {"number": task.number, "max_points": _money(task.max_points)}
        for task in sheet.scheme
    ]
    heading = (
        f"{sheet.title}\n"
        f"scheme: {json.dumps(scheme, ensure_ascii=False)}\n"
        f"statement_pages: {sheet.statement_pages}\n"
        f"solutions_pages: {sheet.solutions_pages}"
    )
    files = await request.get(FileStore)
    return await _images(files, relative, total, start, count, heading)


async def _pages(
    request: AsyncContainer,
    work_ref: str,
    start: int,
    count: int,
) -> list[TextContent | Image]:
    relative, total = await (await request.get(WorkFile))(work_ref)
    files = await request.get(FileStore)
    return await _images(files, relative, total, start, count, "")


async def _images(
    files: FileStore,
    relative: str,
    total: int,
    start: int,
    count: int,
    heading: str,
) -> list[TextContent | Image]:
    path = files.path(relative)
    if not path.is_file():
        # The student deleted their data: the row stays, the PDF does not.
        msg = "the file is gone: skip this work"
        raise ToolError(msg)
    rendered = await render_pages(path, start, count)
    end = start + len(rendered) - 1
    window = f"pages {start}..{end} of {total}"
    text = f"{heading}\n{window}" if heading else window
    blocks: list[TextContent | Image] = [TextContent(type="text", text=text)]
    blocks.extend(Image(data=page, format="jpeg") for page in rendered)
    return blocks


async def _submit(request: AsyncContainer, verdict: VerdictIn) -> VerdictOutcomeOut:
    outcome = await (await request.get(SubmitVerdict))(
        VerdictInput(
            work_ref=verdict.work_ref,
            sha256=verdict.sha256,
            grader=verdict.grader,
            summary=verdict.summary,
            pages_seen=tuple(verdict.pages_seen),
            tasks=tuple(
                TaskInput(
                    task.number,
                    task.points,
                    task.explanation,
                    unreadable=task.unreadable,
                    unsure=task.unsure,
                    manipulation=task.manipulation,
                    pages=tuple(task.pages),
                )
                for task in verdict.tasks
            ),
        ),
    )
    return VerdictOutcomeOut(
        status=outcome.status,
        total=_money(outcome.total),
        max_points=_money(outcome.max_points),
    )


def _money(value: Decimal) -> str:
    text = format(value.quantize(_CENT), "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")
