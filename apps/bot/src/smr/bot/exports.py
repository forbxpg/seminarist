"""The group's sheet as XLSX: names only here, and no cell that could be a formula."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openpyxl import Workbook

from smr.core.clock import MOSCOW
from smr.homework.domain import folder_name

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from smr.gradebook.application.use_cases import SheetRow
    from smr.roster.domain import Group

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def cell(value: object) -> object:
    """Make a value safe for a spreadsheet: text that looks like a formula is quoted.

    Args:
        value: object - A value.

    Returns:
        object - Numbers as they are; text starting like a formula prefixed with `'`.

    """
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return f"'{value}"
    return value


def write_sheet(
    group: Group,
    rows: list[SheetRow],
    folder: Path,
    now: datetime,
) -> Path:
    """Write the sheet of a group.

    Args:
        group: Group - The group.
        rows: list[SheetRow] - Every student's scores.
        folder: Path - The exports folder.
        now: datetime - When; names the file.

    Returns:
        Path - The written file.

    """
    book = Workbook()
    sheet = book.active
    if sheet is None:
        sheet = book.create_sheet()
    sheet.title = "Ведомость"
    types = rows[0].score.parts if rows else ()
    header = [
        "№",
        "ФИО",
        *(f"{p.work_type.title} (из {p.work_type.cap})" for p in types),
    ]
    _ = sheet.append([cell(value) for value in [*header, "Итого", "Место"]])
    for number, row in enumerate(rows, start=1):
        _ = sheet.append(
            [
                number,
                cell(row.student.full_name),
                *(float(part.score) for part in row.score.parts),
                float(row.score.total),
                row.place,
            ],
        )
    folder.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(MOSCOW)
    target = folder / f"{folder_name(group.title)} {stamp:%Y-%m-%d %H-%M}.xlsx"
    book.save(target)
    return target
