"""Seminar materials over a real database and a temporary disk."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER

from smr.materials.application.use_cases import MaterialUpload
from smr.materials.domain import EmptyMaterialError, MaterialNotFoundError

if TYPE_CHECKING:
    from conftest import Materials

    from smr.roster.domain import Group

pytestmark = pytest.mark.integration

PDF = b"%PDF-1.7\n"


async def _group(materials: Materials) -> Group:
    roster = materials.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов")
    ivanov = (await roster.api.students_of(group.group_id))[0]
    _ = await roster.claim(group.invite_code, ivanov.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, ivanov.student_id)
    return group


async def test_a_draft_is_hidden_until_published(materials: Materials) -> None:
    """Students see a card only after publication, and are told once."""
    group = await _group(materials)
    card = await materials.create(TEACHER, group.group_id, "Семинар 4")
    with pytest.raises(EmptyMaterialError):
        await materials.publish(TEACHER, card.material_id)
    _ = await materials.add_file(
        TEACHER,
        card.material_id,
        MaterialUpload(PDF, "tg-pdf"),
    )
    assert await materials.published(STUDENT, group.group_id) == []
    with pytest.raises(MaterialNotFoundError):
        await materials.files_of(STUDENT, card.material_id)

    assert await materials.publish(TEACHER, card.material_id) == 1
    assert [m.title for m in await materials.published(STUDENT, group.group_id)] == [
        "Семинар 4",
    ]
    _, files = await materials.files_of(STUDENT, card.material_id)
    assert [f.tg_file_id for f in files] == ["tg-pdf"]

    await materials.unpublish(TEACHER, card.material_id)
    assert await materials.publish(TEACHER, card.material_id) == 0  # told once already
    kinds = [row.kind for row in await materials.notifications.queued()]
    assert kinds == ["material_published"]


async def test_strangers_see_nothing(materials: Materials) -> None:
    """An account not bound to the group sees no card."""
    group = await _group(materials)
    card = await materials.create(TEACHER, group.group_id, "Семинар 4")
    _ = await materials.add_file(
        TEACHER,
        card.material_id,
        MaterialUpload(PDF, "tg-pdf"),
    )
    _ = await materials.publish(TEACHER, card.material_id)
    assert await materials.published(STUDENT + 1, group.group_id) == []
    with pytest.raises(MaterialNotFoundError):
        await materials.files_of(STUDENT + 1, card.material_id)


async def test_deleting_a_card_deletes_its_files(materials: Materials) -> None:
    """A deleted card leaves nothing on disk."""
    group = await _group(materials)
    card = await materials.create(TEACHER, group.group_id, "Семинар 4")
    file = await materials.add_file(
        TEACHER,
        card.material_id,
        MaterialUpload(PDF, "tg-pdf"),
    )
    await materials.delete(TEACHER, card.material_id)
    assert not materials.files.path(file.path).exists()
    assert await materials.list(TEACHER, group.group_id) == []
