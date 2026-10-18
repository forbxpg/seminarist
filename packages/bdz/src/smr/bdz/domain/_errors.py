"""What a БДЗ can refuse."""

from __future__ import annotations


class BdzError(Exception):
    """Base of the БДЗ errors."""


class BdzNotFoundError(BdzError):
    """There is no such БДЗ."""


class NotYourBdzError(BdzError):
    """The account holds no approved row of this БДЗ's group."""


class InvalidSchemeError(BdzError):
    """The point scheme is not contiguous tasks with positive points."""


class NotAPdfError(BdzError):
    """The file is not a PDF."""


class TooManyPagesError(BdzError):
    """The PDF has more pages than the БДЗ accepts."""


class ConsentRequiredError(BdzError):
    """The student has not accepted the current privacy notice."""


class BdzLockedError(BdzError):
    """Students have already sent work, so the scheme and the files stay."""


class WorkTypeNotProportionalError(BdzError):
    """A БДЗ can only be issued on a proportional work type."""
