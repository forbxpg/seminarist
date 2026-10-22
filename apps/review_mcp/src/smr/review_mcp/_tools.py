"""The four tools: the queue, the pages, and the verdict."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
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
    WorkPages,
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

    from smr.review.application.ports import WorkPage

_REFUSED = (ReviewError, ValueError, PdfBrokenError, PdfLockedError)
_CENT = Decimal("0.01")
_PAGE_LIMIT = 6
_UNREADABLE = "Файл не читается. Пришлите PDF или фото страниц."
_IMAGE_FORMAT = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


@dataclass(frozen=True, slots=True)
class _Slot:
    """One page in the order the agent reads a work.

    Attributes:
        path: str - A FileStore path.
        kind: str - `pdf`, `image` or `unread`.
        number: int - The page inside a PDF. An image is page 1 of itself.

    """

    path: str
    kind: str
    number: int


def register(server: MCPServer, container: AsyncContainer) -> None:
    """Register the grading tools on the server.

    Args:
        server: MCPServer - The server.
        container: AsyncContainer - Where the use cases come from.

    """

    @server.tool()
    async def pending_works(source: str | None = None) -> PendingWorksOut:
        """List live works that have no current verdict.

        Args:
            source: str | None - Only this source. With none, ordinary homework
                is left out until the teacher asks for it by name.

        Returns:
            PendingWorksOut - Oldest first.

        """
        return await _call(container, lambda request: _pending(request, source))

    @server.tool(structured_output=False)
    async def get_task_sheet(
        task_key: str,
        part: Literal["statement", "solutions"],
        start: int = 1,
        count: int = 6,
    ) -> list[TextContent | Image]:
        """Render pages of the statement or the solutions.

        Args:
            task_key: str - `source:<assignment id>`, for example `bdz:` or `homework:`.
            part: Literal["statement", "solutions"] - Which part.
            start: int - The first page, from 1.
            count: int - How many pages, from 1 to 6.

        Returns:
            list[TextContent | Image] - A short text, then one image per page.
                A statement that is only text has no images.

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
        """Render pages of a student's work.

        Args:
            work_ref: str - `source:<version id>`, for example `bdz:` or `homework:`.
            start: int - The first page, from 1.
            count: int - How many pages, from 1 to 6.

        Returns:
            list[TextContent | Image] - A short text, then one image per page.
                A photo is returned as itself. A PDF page is a JPEG.

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


async def _pending(request: AsyncContainer, source: str | None) -> PendingWorksOut:
    found = await (await request.get(PendingWorks))(source)
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
                journal_no=work.journal_no,
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
    elif sheet.solutions_path is None or sheet.solutions_pages is None:
        msg = (
            "no reference solutions: solve every task of the student's variant "
            "yourself before grading"
        )
        raise ToolError(msg)
    else:
        relative, total = sheet.solutions_path, sheet.solutions_pages
    scheme = [
        {"number": task.number, "max_points": _money(task.max_points)}
        for task in sheet.scheme
    ]
    note = f"note: {sheet.note}\n" if sheet.note else ""
    heading = (
        f"{sheet.title}\n"
        f"scheme: {json.dumps(scheme, ensure_ascii=False)}\n"
        f"statement_pages: {sheet.statement_pages}\n"
        f"{note}"
        f"{_solutions_line(sheet.solutions_pages)}"
    )
    if part == "statement" and total == 0:
        return [TextContent(type="text", text=heading)]
    files = await request.get(FileStore)
    return await _images(files, relative, total, start, count, heading)


async def _pages(
    request: AsyncContainer,
    work_ref: str,
    start: int,
    count: int,
) -> list[TextContent | Image]:
    found, total = await (await request.get(WorkPages))(work_ref)
    files = await request.get(FileStore)
    return await _work_images(files, found, total, start, count)


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


async def _work_images(
    files: FileStore,
    pages: tuple[WorkPage, ...],
    total: int,
    start: int,
    count: int,
) -> list[TextContent | Image]:
    slots = _slots(pages)
    if count < 1 or count > _PAGE_LIMIT:
        msg = "count is from 1 to 6"
        raise ValueError(msg)
    if start < 1 or start > len(slots):
        msg = "start is past the last page"
        raise ValueError(msg)
    window = slots[start - 1 : start + count - 1]
    if any(slot.kind == "unread" for slot in window):
        raise ToolError(_UNREADABLE)
    rendered: list[Image] = []
    for slot in window:
        path = files.path(slot.path)
        if not path.is_file():
            msg = "the file is gone: skip this work"
            raise ToolError(msg)
        if slot.kind == "pdf":
            page = await render_pages(path, slot.number, 1)
            rendered.append(Image(data=page[0], format="jpeg"))
        else:
            data = await asyncio.to_thread(path.read_bytes)
            image_format = _IMAGE_FORMAT.get(path.suffix, "jpeg")
            rendered.append(Image(data=data, format=image_format))
    end = start + len(window) - 1
    blocks: list[TextContent | Image] = [
        TextContent(type="text", text=f"pages {start}..{end} of {total}"),
    ]
    blocks.extend(rendered)
    return blocks


def _slots(pages: tuple[WorkPage, ...]) -> list[_Slot]:
    slots: list[_Slot] = []
    for page in pages:
        if page.kind == "pdf":
            slots.extend(
                _Slot(page.path, "pdf", number)
                for number in range(1, page.pdf_pages + 1)
            )
            continue
        slots.append(_Slot(page.path, page.kind, 1))
    return slots


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


def _solutions_line(pages: int | None) -> str:
    if pages is None:
        return "solutions: none, solve the tasks yourself"
    return f"solutions_pages: {pages}"
