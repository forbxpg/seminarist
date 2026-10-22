"""Use cases of a БДЗ."""

from __future__ import annotations

from smr.bdz.domain import BdzDraft

from ._export import ExportBdz
from ._files import DeleteGroupBdzFiles, DeleteStudentBdzFiles
from ._limits import BdzLimits
from ._student import BdzStatement, SendBdz, StudentBdz, StudentBdzList
from ._teacher import (
    BdzRoster,
    BdzSummary,
    CreateBdz,
    DeleteBdz,
    ListBdz,
    MoveBdz,
    RosterLine,
    UpdateBdzDeadline,
)
from ._upload import Upload

__all__ = (
    "BdzDraft",
    "BdzLimits",
    "BdzRoster",
    "BdzStatement",
    "BdzSummary",
    "CreateBdz",
    "DeleteBdz",
    "DeleteGroupBdzFiles",
    "DeleteStudentBdzFiles",
    "ExportBdz",
    "ListBdz",
    "MoveBdz",
    "RosterLine",
    "SendBdz",
    "StudentBdz",
    "StudentBdzList",
    "UpdateBdzDeadline",
    "Upload",
)
