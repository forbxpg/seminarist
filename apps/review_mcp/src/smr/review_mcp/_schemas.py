"""What the grading tools accept and return."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class PendingWorkOut(BaseModel):
    """One live version the agent has not graded yet."""

    work_ref: str
    task_key: str
    title: str
    version: int
    pages: int
    sha256: str
    is_late: bool
    journal_no: int | None


class PendingWorksOut(BaseModel):
    """Every live version that has no current verdict."""

    works: list[PendingWorkOut]


class TaskIn(BaseModel):
    """One task as the agent scored it."""

    number: int = Field(ge=1)
    points: Decimal = Field(ge=0)
    explanation: str
    unreadable: bool = False
    unsure: bool = False
    manipulation: bool = False
    pages: list[int] = Field(default_factory=list)


class VerdictIn(BaseModel):
    """A verdict as the agent submits it."""

    work_ref: str
    sha256: str
    grader: str
    summary: str = ""
    pages_seen: list[int]
    tasks: list[TaskIn]


class VerdictOutcomeOut(BaseModel):
    """What submitting a verdict did."""

    status: str
    total: str
    max_points: str
