"""Every dialog's states."""

from __future__ import annotations

from typing import final

from aiogram.fsm.state import State, StatesGroup


@final
class JoinSG(StatesGroup):
    """A student joins a group by its link."""

    consent = State()
    pick = State()
    confirm = State()
    waiting = State()


@final
class StudentSG(StatesGroup):
    """A bound student's menu."""

    groups = State()
    menu = State()
    homework = State()
    assignment = State()
    upload = State()
    homework_verdict = State()
    homework_appeal = State()
    homework_appeal_confirm = State()
    materials = State()
    scores = State()
    settings = State()
    forget = State()
    bdz_list = State()
    bdz = State()
    bdz_upload = State()
    bdz_verdict = State()
    bdz_appeal = State()
    bdz_appeal_confirm = State()


@final
class AdminSG(StatesGroup):
    """The teacher's top menu and groups."""

    menu = State()
    groups = State()
    new_title = State()
    new_subject = State()
    new_semester = State()
    group = State()
    roster = State()
    roster_paste = State()
    student = State()
    journal_no = State()
    invite = State()
    settings = State()
    setting_value = State()
    archive = State()
    pending = State()


@final
class SessionsSG(StatesGroup):
    """The teacher at a session: attendance and the board."""

    list = State()
    new_when = State()
    new_topic = State()
    edit_when = State()
    edit_topic = State()
    session = State()
    attendance = State()
    board = State()
    drawn = State()
    calls = State()
    grade = State()


@final
class HomeworkSG(StatesGroup):
    """The teacher's assignments and grading."""

    list = State()
    new_title = State()
    new_body = State()
    new_deadline = State()
    new_points = State()
    new_file = State()
    new_confirm = State()
    assignment = State()
    review = State()
    grade = State()
    roster = State()
    copy = State()
    copy_deadline = State()
    delete = State()


@final
class MaterialsSG(StatesGroup):
    """The teacher's seminar cards."""

    list = State()
    new_title = State()
    card = State()
    upload = State()
    publish = State()
    delete = State()


@final
class GradebookSG(StatesGroup):
    """The teacher's scheme, tests and loose points."""

    types = State()
    work_type = State()
    new_title = State()
    new_kind = State()
    new_cap = State()
    cap = State()
    items = State()
    new_item_title = State()
    new_item_points = State()
    grading = State()
    grade_value = State()
    points_student = State()
    points_value = State()


@final
class BdzSG(StatesGroup):
    """The teacher's БДЗ: the list, the card and the creation wizard."""

    list = State()
    card = State()
    new_title = State()
    new_type = State()
    new_statement = State()
    new_solutions = State()
    new_scheme = State()
    new_deadline = State()
    new_confirm = State()
    deadline = State()
    move = State()
    roster = State()
    delete = State()


@final
class ReviewSG(StatesGroup):
    """The teacher's queue of manual checks and appeals."""

    queue = State()
    item = State()
    grade = State()
    comment = State()
    confirm = State()


@final
class ConsentSG(StatesGroup):
    """A student accepts the current privacy notice again."""

    renew = State()
