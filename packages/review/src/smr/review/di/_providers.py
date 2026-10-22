"""The review's repositories, contract and use cases, for every app."""

from __future__ import annotations

from typing import final

from dishka import Provider, Scope, provide, provide_all

from smr.review.application.contracts import ReviewApi
from smr.review.application.ports import AppealRepository, VerdictRepository
from smr.review.application.services import Reviews
from smr.review.application.use_cases import (
    FileAppeal,
    FinalizeByTeacher,
    FlagUnreadable,
    MyVerdict,
    OpenForTeacher,
    PendingWorks,
    SubmitVerdict,
    TaskSheetFor,
    TeacherQueue,
    WorkFile,
    WorkPages,
)
from smr.review.infrastructure.repositories import SqlAlchemyAppeals, SqlAlchemyVerdicts


@final
class ReviewProvider(Provider):
    """Everything of the review except the sources of work.

    An app that wires the review also provides `Sequence[ReviewSource]`.
    """

    scope = Scope.REQUEST

    verdicts = provide(SqlAlchemyVerdicts, provides=VerdictRepository)
    appeals = provide(SqlAlchemyAppeals, provides=AppealRepository)
    api = provide(Reviews, provides=ReviewApi)

    use_cases = provide_all(
        FileAppeal,
        FinalizeByTeacher,
        FlagUnreadable,
        MyVerdict,
        OpenForTeacher,
        PendingWorks,
        SubmitVerdict,
        TaskSheetFor,
        TeacherQueue,
        WorkFile,
        WorkPages,
    )
