"""The outbox over a real database."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from roster_kit import STUDENT, TEACHER

from smr.notifications.domain import NotificationKind

if TYPE_CHECKING:
    from notifications_kit import Notifications
    from roster_kit import Roster

    from smr.roster.domain import Group

pytestmark = pytest.mark.integration

PAYLOAD = {"title": "Семинар 4", "group": "К01-261"}


async def _group(roster: Roster) -> Group:
    group = await roster.create(
        TEACHER,
        title="К01-261",
        subject="ДМ",
        semester="осень 2026",
    )
    _ = await roster.import_(TEACHER, group.group_id, "Иванов\nПетров\nСидоров")
    first, second, _ = await roster.api.students_of(group.group_id)
    _ = await roster.claim(group.invite_code, first.student_id, STUDENT, "v1")
    _ = await roster.approve(TEACHER, first.student_id)
    _ = await roster.claim(group.invite_code, second.student_id, STUDENT + 1, "v1")
    return group


async def test_group_notice_reaches_only_the_bound(
    roster: Roster,
    notifications: Notifications,
) -> None:
    """The pending and the unbound are not told; a repeat is skipped."""
    group = await _group(roster)
    notifier = notifications.notifier
    assert (
        await notifier.notify_group(
            group.group_id,
            NotificationKind.MATERIAL_PUBLISHED,
            PAYLOAD,
            "m:1",
        )
        == 1
    )
    _ = await notifier.notify_group(
        group.group_id,
        NotificationKind.MATERIAL_PUBLISHED,
        PAYLOAD,
        "m:1",
    )
    assert [row.tg_user_id for row in await notifications.queued()] == [STUDENT]


async def test_delivery_sends_retries_and_gives_up(
    roster: Roster,
    notifications: Notifications,
) -> None:
    """A busy Telegram is retried; a blocked account is given up on."""
    _ = await _group(roster)
    notifier = notifications.notifier
    await notifier.notify_account(
        STUDENT,
        NotificationKind.BINDING_APPROVED,
        {"group": "К01"},
    )
    await notifier.notify_account(
        STUDENT + 1,
        NotificationKind.BINDING_REJECTED,
        {"group": "К01"},
    )
    notifications.sender.busy_once.add(STUDENT)
    notifications.sender.blocked.add(STUDENT + 1)
    report = await notifications.deliver()
    assert (report.sent, report.failed, report.gave_up) == (1, 0, 1)
    assert [tg for tg, _ in notifications.sender.sent] == [STUDENT]
    again = await notifications.deliver()
    assert (again.sent, again.failed, again.gave_up) == (0, 0, 0)


async def test_admins_are_told_of_requests(notifications: Notifications) -> None:
    """A binding request goes to every teacher."""
    await notifications.notifier.notify_admins(
        NotificationKind.BINDING_REQUESTED,
        {"group": "К01", "name": "Иванов"},
    )
    assert [row.tg_user_id for row in await notifications.queued()] == [TEACHER]


async def test_reminders_can_be_muted(
    roster: Roster,
    notifications: Notifications,
) -> None:
    """A student who turns reminders off is listed as muted."""
    group = await _group(roster)
    first = (await roster.api.students_of(group.group_id))[0]
    await notifications.set_reminders(STUDENT, enabled=False)
    assert await notifications.notifier.muted([first.student_id]) == {first.student_id}
    await notifications.set_reminders(STUDENT, enabled=True)
    assert await notifications.notifier.muted([first.student_id]) == set()
