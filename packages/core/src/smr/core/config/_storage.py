"""Where the files of the seminars live on disk."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class StorageSettings(BaseSettings):
    """Storage settings.

    Attributes:
        data_dir: Path - Root of the files: homework, seminar PDFs, exports.
        backup_dir: Path - Where the daily backups go; best synced off the machine.
        max_file_bytes: int - Largest accepted file; Telegram lets a bot download 20 MB.
        max_files_per_submission: int - Most files one homework submission may hold.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("STORAGE_")

    data_dir: Path
    backup_dir: Path
    max_file_bytes: int = 20 * 1024 * 1024
    max_files_per_submission: int = 20
