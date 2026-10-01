"""A migrated PostgreSQL for integration tests, started once per session by testcontainers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

_ROOT = Path(__file__).resolve().parents[4]
_IMAGE = "postgres:17-alpine"


def migrate(url: str) -> None:
    """Apply every revision to an empty database.

    Args:
        url: str - `postgresql+asyncpg://` URL.

    """
    config = Config(str(_ROOT / "alembic.ini"))
    config.attributes["url"] = url
    command.upgrade(config, "heads")


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Start PostgreSQL, migrate it and give its URL.

    Yields:
        str - `postgresql+asyncpg://` URL of the migrated database.

    """
    with PostgresContainer(_IMAGE, driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        migrate(url)
        yield url


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    """Give a session inside a transaction rolled back after the test.

    Commits inside the test become savepoints, so use cases commit as usual.

    Yields:
        AsyncSession - The session.

    """
    engine = create_async_engine(database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )
        finally:
            await transaction.rollback()
    await engine.dispose()
