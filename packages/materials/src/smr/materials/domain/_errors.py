"""Errors of materials."""

from __future__ import annotations


class MaterialsError(Exception):
    """Base of materials' errors."""


class MaterialNotFoundError(MaterialsError):
    """No such card, or not one the asking student may see."""


class EmptyMaterialError(MaterialsError):
    """A card without files cannot be published."""


class NotPublishedError(MaterialsError):
    """The card is a draft: students cannot see it yet."""
