"""Errors of the ledger."""

from __future__ import annotations


class GradebookError(Exception):
    """Base of the ledger's errors."""


class WorkTypeNotFoundError(GradebookError):
    """No such work type."""


class WorkTypeInUseError(GradebookError):
    """The work type still has points; it cannot be deleted."""


class WorkTypeKindTakenError(GradebookError):
    """The group already has a work type of this kind, and only one is allowed."""


class ItemNotFoundError(GradebookError):
    """No such graded item."""


class EntryNotFoundError(GradebookError):
    """No such entry of the ledger."""


class PointsOutOfRangeError(GradebookError):
    """Points below zero or above the maximum."""
