"""The grading server over a real database, through the in-process client."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from dishka import Provider, Scope, provide
from mcp.client import Client
from pydantic import SecretStr
from pypdf import PdfWriter

from smr.bdz.application.use_cases import (
    BdzDraft,
    CreateBdz,
    DeleteBdz,
    SendBdz,
    Upload,
)
from smr.core.config import DatabaseSettings, StorageSettings, TelegramSettings
from smr.gradebook.application.use_cases import ApplyDefaultScheme
from smr.gradebook.domain import WorkTypeKind
from smr.review.domain import SchemeTask
from smr.review_mcp import build_server, make_container
from smr.roster.application.use_cases import (
    AcceptConsent,
    ApproveBinding,
    ClaimStudent,
    CreateGroup,
    ImportRoster,
    ListStudents,
)

if TYPE_CHECKING:
    from pathlib import Path

    from dishka import AsyncContainer

pytestmark = pytest.mark.integration

_TEACHER = 1
_STUDENT = 500


class _Settings(Provider):
    """Point the server at the test database and an empty directory."""

    def __init__(self, url: str, directory: Path) -> None:
        super().__init__()
        self._url: str = url
        self._directory: Path = directory

    @provide(scope=Scope.APP, override=True)
    def database_settings(self) -> DatabaseSettings:
        """The test database.

        Returns:
            DatabaseSettings - The container's URL.

        """
        return DatabaseSettings.model_validate({"url": self._url})

    @provide(scope=Scope.APP, override=True)
    def storage_settings(self) -> StorageSettings:
        """Files under the test directory.

        Returns:
            StorageSettings - The temporary root.

        """
        return StorageSettings(
            data_dir=self._directory,
            backup_dir=self._directory,
        )

    @provide(scope=Scope.APP, override=True)
    def telegram_settings(self) -> TelegramSettings:
        """One teacher, and a token the server never uses.

        Returns:
            TelegramSettings - Teacher id 1.

        """
        return TelegramSettings(
            bot_token=SecretStr("1:test"),
            admin_ids=frozenset({_TEACHER}),
        )


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def _work(container: AsyncContainer) -> tuple[str, str, str]:
    """Publish a БДЗ and send one PDF.

    Returns:
        tuple[str, str, str] - The work ref, the task key and the file hash.

    """
    now = datetime.now(UTC)
    pdf = _pdf()
    async with container() as request:
        group = await (await request.get(CreateGroup))(
            _TEACHER,
            title="К01-261",
            subject="ДМ",
            semester="осень 2026",
        )
        _ = await (await request.get(ImportRoster))(_TEACHER, group.group_id, "Иванов")
        student = next(
            iter(await (await request.get(ListStudents))(_TEACHER, group.group_id)),
        )
        _ = await (await request.get(ClaimStudent))(
            group.invite_code,
            student.student_id,
            _STUDENT,
            "v1",
        )
        _ = await (await request.get(ApproveBinding))(_TEACHER, student.student_id)
        _ = await (await request.get(AcceptConsent))(_STUDENT)
        types = await (await request.get(ApplyDefaultScheme))(_TEACHER, group.group_id)
        work_type = next(item for item in types if item.kind is WorkTypeKind.TEST)
        created = await (await request.get(CreateBdz))(
            _TEACHER,
            group.group_id,
            BdzDraft(
                "Контрольная",
                now + timedelta(days=2),
                work_type.work_type_id,
                (SchemeTask(1, Decimal(10)),),
            ),
            Upload(pdf, "tg-s", "uniq-s", now),
            Upload(pdf, "tg-a", "uniq-a", now),
        )
        sent = await (await request.get(SendBdz))(
            _STUDENT,
            created.bdz_id,
            Upload(pdf, "tg-w", "uniq-w", now),
        )
    return (
        f"bdz:{sent.submission_id}",
        f"bdz:{created.bdz_id}",
        sent.sha256,
    )


async def _forget(container: AsyncContainer, task_key: str) -> None:
    bdz_id = uuid.UUID(task_key.split(":", maxsplit=1)[1])
    async with container() as request:
        await (await request.get(DeleteBdz))(_TEACHER, bdz_id)


async def test_lists_four_tools(database_url: str, tmp_path: Path) -> None:
    """The server exposes the four grading tools."""
    container = make_container(_Settings(database_url, tmp_path))
    try:
        async with Client(build_server(container)) as client:
            listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
    finally:
        await container.close()
    assert names == {
        "pending_works",
        "get_task_sheet",
        "get_work_pages",
        "submit_verdict",
    }


async def test_pending_then_pages_then_verdict(
    database_url: str,
    tmp_path: Path,
) -> None:
    """A live PDF is listed, rendered, and then graded."""
    container = make_container(_Settings(database_url, tmp_path))
    work_ref, task_key, sha = await _work(container)
    try:
        async with Client(build_server(container)) as client:
            pending = await client.call_tool("pending_works")
            pages = await client.call_tool(
                "get_work_pages",
                {"work_ref": work_ref, "start": 1, "count": 1},
            )
            verdict = await client.call_tool(
                "submit_verdict",
                {
                    "verdict": {
                        "work_ref": work_ref,
                        "sha256": sha,
                        "grader": "m",
                        "summary": "",
                        "pages_seen": [1],
                        "tasks": [
                            {
                                "number": 1,
                                "points": "7",
                                "explanation": "Верно.",
                                "pages": [1],
                            },
                        ],
                    },
                },
            )
    finally:
        await _forget(container, task_key)
        await container.close()
    assert pending.structured_content is not None
    assert pending.structured_content["works"][0]["work_ref"] == work_ref
    assert [block.type for block in pages.content] == ["text", "image"]
    assert verdict.structured_content is not None
    assert verdict.structured_content["status"] == "published"


async def test_refusal_carries_reason(database_url: str, tmp_path: Path) -> None:
    """A verdict that misses a task comes back with the reason."""
    container = make_container(_Settings(database_url, tmp_path))
    work_ref, task_key, sha = await _work(container)
    try:
        async with Client(build_server(container)) as client:
            refused = await client.call_tool(
                "submit_verdict",
                {
                    "verdict": {
                        "work_ref": work_ref,
                        "sha256": sha,
                        "grader": "m",
                        "pages_seen": [1],
                        "tasks": [],
                    },
                },
            )
    finally:
        await _forget(container, task_key)
        await container.close()
    assert refused.is_error
    text = " ".join(block.text for block in refused.content if block.type == "text")
    assert "missing tasks" in text
