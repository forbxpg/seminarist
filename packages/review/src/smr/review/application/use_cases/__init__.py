"""Use cases of the review."""

from __future__ import annotations

from ._agent import (
    PendingWork,
    PendingWorks,
    SubmitVerdict,
    TaskInput,
    TaskSheetFor,
    VerdictInput,
    VerdictOutcome,
    WorkFile,
    WorkPages,
)
from ._flag import FlagUnreadable
from ._student import FileAppeal, MyVerdict, VerdictView
from ._teacher import (
    FinalizeByTeacher,
    OpenForTeacher,
    QueueItem,
    TeacherQueue,
    TeacherView,
)

__all__ = (
    "FileAppeal",
    "FinalizeByTeacher",
    "FlagUnreadable",
    "MyVerdict",
    "OpenForTeacher",
    "PendingWork",
    "PendingWorks",
    "QueueItem",
    "SubmitVerdict",
    "TaskInput",
    "TaskSheetFor",
    "TeacherQueue",
    "TeacherView",
    "VerdictInput",
    "VerdictOutcome",
    "VerdictView",
    "WorkFile",
    "WorkPages",
)
