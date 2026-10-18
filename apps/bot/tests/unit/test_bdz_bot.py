"""Scores a teacher types, and the verdict text a student reads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from smr.bot.parsing import parse_scores
from smr.bot.verdicts import verdict_messages
from smr.review.application.use_cases import VerdictView
from smr.review.domain import GraderKind, TaskVerdict, Verdict, VerdictStatus


def test_parse_scores() -> None:
    """Pairs separated by commas, spaces or newlines, with `:` or `=`."""
    scores = parse_scores("1:3, 2:2.5\n3=0", [1, 2, 3])
    assert scores == {1: Decimal(3), 2: Decimal("2.5"), 3: Decimal(0)}


@pytest.mark.parametrize(
    ("text", "numbers", "problem"),
    [
        ("1:3, 2:1", [1, 2, 3], "missing"),
        ("1:3, 2:1, 4:1", [1, 2], "extra"),
        ("1:3, 1:2", [1], "duplicate"),
        ("1:-1", [1], "negative"),
    ],
)
def test_parse_scores_refuses(text: str, numbers: list[int], problem: str) -> None:
    """A missing, extra, repeated or negative score is named."""
    with pytest.raises(ValueError, match=problem):
        _ = parse_scores(text, numbers)


def test_verdict_text_escapes_explanations() -> None:
    """A title and an explanation cannot break the HTML."""
    view = _view(
        summary="a < b",
        tasks=(_task(1, "1 < 2 & 3"),),
    )
    text = verdict_messages(view, title="A < B")[0]
    assert "<b>A &lt; B</b>" in text
    assert "1 &lt; 2 &amp; 3" in text
    assert "a &lt; b" in text


def test_verdict_text_splits_between_tasks() -> None:
    """Long breakdowns split on task boundaries and keep tags balanced."""
    tasks = tuple(_task(number, "я" * 200) for number in range(1, 41))
    messages = verdict_messages(_view(summary="", tasks=tasks), title="К")
    assert len(messages) >= 2
    for message in messages:
        assert len(message) <= 4096
        assert message.count("<b>") == message.count("</b>")


def test_verdict_text_cuts_a_block_that_does_not_fit() -> None:
    """One block longer than the limit is cut and marked."""
    messages = verdict_messages(
        _view(summary="", tasks=(_task(1, "я" * 50),)),
        title="К",
        limit=40,
    )
    assert messages[-1].endswith("…")
    assert all(len(message) <= 40 for message in messages)


def _task(number: int, explanation: str) -> TaskVerdict:
    return TaskVerdict(
        number=number,
        points=Decimal(1),
        max_points=Decimal(1),
        explanation=explanation,
        unreadable=False,
        unsure=False,
        manipulation=False,
        pages=(1,),
    )


def _view(*, summary: str, tasks: tuple[TaskVerdict, ...]) -> VerdictView:
    total = sum((task.points for task in tasks), Decimal(0))
    maximum = sum((task.max_points for task in tasks), Decimal(0))
    verdict = Verdict(
        verdict_id=uuid.uuid4(),
        source="bdz",
        work_id=uuid.uuid4(),
        work_sha256="abc",
        task_ref=uuid.uuid4(),
        student_ref=uuid.uuid4(),
        grader_kind=GraderKind.AGENT,
        grader="m",
        status=VerdictStatus.PUBLISHED,
        total=total,
        max_points=maximum,
        summary=summary,
        pages_seen=1,
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
        published_at=datetime(2026, 10, 18, tzinfo=UTC),
        tasks=tasks,
    )
    return VerdictView(verdict, can_appeal=True, appeal_until=None, appeal=None)
