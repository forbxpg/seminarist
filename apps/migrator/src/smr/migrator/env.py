"""Alembic environment: one chain for every package, one transaction per revision."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from alembic import context
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import create_async_engine

from smr.core.config import DatabaseSettings
from smr.migrator import all_metadata

if TYPE_CHECKING:
    from sqlalchemy import MetaData

VERSION_SCHEMA = "migrations"

_metadata = all_metadata()
_schemas = {metadata.schema for metadata in _metadata}


def _include_name(name: str | None, type_: str, _parents: object) -> bool:
    return type_ != "schema" or name in _schemas


def _run(connection: Connection) -> None:
    _ = connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_SCHEMA}"))
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=cast("MetaData", cast("object", _metadata)),
        include_schemas=True,
        include_name=_include_name,
        version_table_schema=VERSION_SCHEMA,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _online(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


_shared = context.config.attributes.get("connection")
if isinstance(_shared, Connection):
    _run(_shared)
else:
    _url = context.config.attributes.get("url")
    if not isinstance(_url, str):
        _url = str(DatabaseSettings().url)  # pyright: ignore[reportCallIssue] -- read from the environment
    asyncio.run(_online(_url))
