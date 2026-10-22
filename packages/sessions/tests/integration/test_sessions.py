"""Sessions, attendance and the board over a real database."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from roster_kit import TEACHER

from smr.core.clock import MOSCOW
from smr.gradebook.infrastructure.repositories import SqlAlchemyEntries, SqlAlchemyItems
from smr.sessions.domain import AttendanceStatus, BoardMode, NoCandidatesError
from smr.sessions.infrastructure.repositories import SqlAlchemySessions

if TYPE_CHECKING:
    import uuid

    from sessions_kit import Sessions
    from sqlalchemy.ext.asyncio import AsyncSession

    from smr.roster.domain import Group, Student
    from smr.sessions.domain import Session

pytestmark = pytest.mark.integration


async def _setup(sessions: Sessions) -> tuple[Group, list[Student], Session]:
    roster = sessions.gradebook.roster
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов\nПетров\nСидоров")
    _ = await sessions.gradebook.scheme(TEACHER, group.group_id)
    students = list(await roster.api.students_of(group.group_id))
    seminar = await sessions.create(
        TEACHER,
        group.group_id,
        starts_at=roster.clock.now(),
        topic="Нормальные формы",
    )
    return group, students, seminar


async def _totals(sessions: Sessions, group: Group) -> dict[str, Decimal]:
    rows = await sessions.gradebook.sheet(TEACHER, group.group_id)
    return {row.student.full_name: row.score.total for row in rows}


async def test_unmarked_attendance_proposes_everyone_present(
    sessions: Sessions,
) -> None:
    """Before saving, the sheet proposes all present."""
    _, _, seminar = await _setup(sessions)
    sheet = await sessions.sheet(TEACHER, seminar.session_id)
    assert {status for _, status in sheet} == {AttendanceStatus.PRESENT}


async def test_attendance_scores_the_ledger(sessions: Sessions) -> None:
    """Present gets the attendance points, absent none, excused keeps a full score."""
    group, (ivanov, petrov, sidorov), seminar = await _setup(sessions)
    await sessions.mark(
        TEACHER,
        seminar.session_id,
        {
            ivanov.student_id: AttendanceStatus.PRESENT,
            petrov.student_id: AttendanceStatus.ABSENT,
            sidorov.student_id: AttendanceStatus.EXCUSED,
        },
    )
    totals = await _totals(sessions, group)
    assert totals == {"Иванов": Decimal(4), "Петров": Decimal(0), "Сидоров": Decimal(0)}
    await sessions.mark(
        TEACHER,
        seminar.session_id,
        {petrov.student_id: AttendanceStatus.PRESENT},
    )
    assert (await _totals(sessions, group))["Петров"] == Decimal(4)


async def test_candidates_exclude_the_absent_and_the_called(sessions: Sessions) -> None:
    """The absent and those already called are not candidates."""
    _, (ivanov, petrov, sidorov), seminar = await _setup(sessions)
    await sessions.mark(
        TEACHER,
        seminar.session_id,
        {petrov.student_id: AttendanceStatus.ABSENT},
    )
    _ = await sessions.call(
        TEACHER,
        seminar.session_id,
        ivanov.student_id,
        BoardMode.MANUAL,
        "1.19",
    )
    candidates = await sessions.candidates(TEACHER, seminar.session_id)
    assert [c.student.student_id for c in candidates] == [sidorov.student_id]
    assert candidates[0].probability == pytest.approx(1)


async def test_draw_runs_out(sessions: Sessions) -> None:
    """Once everyone present has been called, the draw says so."""
    _, students, seminar = await _setup(sessions)
    for _ in students:
        drawn = await sessions.draw(TEACHER, seminar.session_id)
        _ = await sessions.call(
            TEACHER,
            seminar.session_id,
            drawn.student.student_id,
            BoardMode.RANDOM,
            None,
        )
    with pytest.raises(NoCandidatesError):
        await sessions.draw(TEACHER, seminar.session_id)


async def test_board_points_and_their_correction(sessions: Sessions) -> None:
    """Grading a call adds board points; regrading changes them; deleting removes them."""
    group, (ivanov, _, _), seminar = await _setup(sessions)
    call = await sessions.call(
        TEACHER,
        seminar.session_id,
        ivanov.student_id,
        BoardMode.MANUAL,
        None,
    )
    graded = await sessions.grade(TEACHER, call.call_id, Decimal(2), "хорошо")
    assert (await _totals(sessions, group))["Иванов"] == Decimal(2)
    _ = await sessions.grade(TEACHER, graded.call_id, Decimal(1), None)
    assert (await _totals(sessions, group))["Иванов"] == Decimal(1)
    await sessions.delete_call(TEACHER, call.call_id)
    assert (await _totals(sessions, group))["Иванов"] == Decimal(0)


async def test_rarely_called_are_likelier(sessions: Sessions) -> None:
    """A student called at earlier sessions has a lower chance at the next one."""
    group, (ivanov, petrov, _), first = await _setup(sessions)
    _ = await sessions.call(
        TEACHER,
        first.session_id,
        ivanov.student_id,
        BoardMode.MANUAL,
        None,
    )
    roster = sessions.gradebook.roster
    second = await sessions.create(
        TEACHER,
        group.group_id,
        starts_at=roster.clock.now(),
        topic="СДНФ",
    )
    chances = {
        c.student.student_id: c.probability
        for c in await sessions.candidates(TEACHER, second.session_id)
    }
    assert chances[petrov.student_id] > chances[ivanov.student_id]


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=MOSCOW).astimezone(UTC)


async def _titles(db: AsyncSession, *session_ids: uuid.UUID) -> list[str]:
    stored = SqlAlchemySessions(db)
    items = SqlAlchemyItems(db)
    titles: list[str] = []
    for session_id in session_ids:
        found = await stored.get(session_id)
        assert found is not None
        assert found.attendance_item_id is not None
        item = await items.get(found.attendance_item_id)
        assert item is not None
        titles.append(item.title)
    return titles


async def test_one_session_a_day_is_labelled_by_date(
    sessions: Sessions,
    session: AsyncSession,
) -> None:
    """A lone session keeps the date-only ledger line."""
    group, (ivanov, _, _), _seminar = await _setup(sessions)
    morning = await sessions.create(
        TEACHER,
        group.group_id,
        starts_at=_at(8, 10),
        topic="Утро",
    )
    await sessions.mark(
        TEACHER,
        morning.session_id,
        {ivanov.student_id: AttendanceStatus.PRESENT},
    )
    assert await _titles(session, morning.session_id) == ["Занятие 08.10"]


async def test_two_sessions_one_day_are_labelled_with_time(
    sessions: Sessions,
    session: AsyncSession,
) -> None:
    """A second session the same day adds the clock time to both lines, points stay."""
    group, (ivanov, _, _), _seminar = await _setup(sessions)
    morning = await sessions.create(
        TEACHER,
        group.group_id,
        starts_at=_at(8, 10),
        topic="Утро",
    )
    await sessions.mark(
        TEACHER,
        morning.session_id,
        {ivanov.student_id: AttendanceStatus.PRESENT},
    )
    morning_row = await SqlAlchemySessions(session).get(morning.session_id)
    assert morning_row is not None
    morning_item_id = morning_row.attendance_item_id
    assert morning_item_id is not None
    morning_points = await SqlAlchemyEntries(session).for_item(
        ivanov.student_id,
        morning_item_id,
    )
    assert morning_points is not None
    assert morning_points.points == Decimal(1)
    afternoon = await sessions.create(
        TEACHER,
        group.group_id,
        starts_at=_at(8, 14, 30),
        topic="День",
    )
    await sessions.mark(
        TEACHER,
        afternoon.session_id,
        {ivanov.student_id: AttendanceStatus.ABSENT},
    )
    assert await _titles(session, morning.session_id, afternoon.session_id) == [
        "Занятие 08.10 10:00",
        "Занятие 08.10 14:30",
    ]
    kept = await SqlAlchemyEntries(session).for_item(
        ivanov.student_id,
        morning_item_id,
    )
    assert kept is not None
    assert kept.entry_id == morning_points.entry_id
    assert kept.points == Decimal(1)
    assert kept.excused is False


async def test_deleting_a_session_takes_its_points(sessions: Sessions) -> None:
    """A deleted session leaves no attendance or board points behind."""
    group, (ivanov, _, _), seminar = await _setup(sessions)
    await sessions.mark(
        TEACHER,
        seminar.session_id,
        {ivanov.student_id: AttendanceStatus.PRESENT},
    )
    call = await sessions.call(
        TEACHER,
        seminar.session_id,
        ivanov.student_id,
        BoardMode.MANUAL,
        None,
    )
    _ = await sessions.grade(TEACHER, call.call_id, Decimal(2), None)
    await sessions.delete(TEACHER, seminar.session_id)
    assert (await _totals(sessions, group))["Иванов"] == Decimal(0)
