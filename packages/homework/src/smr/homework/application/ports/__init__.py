"""Where assignments, submissions and their files are kept."""

from __future__ import annotations

from ._ports import AssignmentRepository, FileRepository, SubmissionRepository

__all__ = ("AssignmentRepository", "FileRepository", "SubmissionRepository")
