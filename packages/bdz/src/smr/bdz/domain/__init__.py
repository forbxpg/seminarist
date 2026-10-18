"""The rules of a БДЗ."""

from __future__ import annotations

from ._entities import Bdz, BdzDraft, BdzSubmission
from ._enums import SubmissionStatus
from ._errors import (
    BdzError,
    BdzLockedError,
    BdzNotFoundError,
    ConsentRequiredError,
    InvalidSchemeError,
    NotAPdfError,
    NotYourBdzError,
    TooManyPagesError,
    WorkTypeNotProportionalError,
)
from ._folders import folder_name
from ._scheme import parse_scheme

__all__ = (
    "Bdz",
    "BdzDraft",
    "BdzError",
    "BdzLockedError",
    "BdzNotFoundError",
    "BdzSubmission",
    "ConsentRequiredError",
    "InvalidSchemeError",
    "NotAPdfError",
    "NotYourBdzError",
    "SubmissionStatus",
    "TooManyPagesError",
    "WorkTypeNotProportionalError",
    "folder_name",
    "parse_scheme",
)
