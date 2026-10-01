"""Settings, database, audit, files and clock for every app."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import final

from dishka import Provider, Scope, ValidationSettings, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from smr.core.audit import AuditLog, SqlAlchemyAuditLog
from smr.core.clock import Clock, SystemClock
from smr.core.config import (
    DatabaseSettings,
    RedisSettings,
    StorageSettings,
    TelegramSettings,
)
from smr.core.database import (
    SqlAlchemyUnitOfWork,
    UnitOfWork,
    create_engine,
    create_session_factory,
)
from smr.core.files import FileStore

CONTAINER_VALIDATION = ValidationSettings(implicit_override=True)


@final
class CoreProvider(Provider):
    """The kernel's dependencies.

    Settings have required fields pydantic reads from the environment; basedpyright
    only sees a constructor call with missing arguments, hence the ignores.
    """

    @provide(scope=Scope.APP)
    def database_settings(self) -> DatabaseSettings:
        """Read the database settings.

        Returns:
            DatabaseSettings - From `DATABASE_*`.

        """
        return DatabaseSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    def redis_settings(self) -> RedisSettings:
        """Read the Redis settings.

        Returns:
            RedisSettings - From `REDIS_*`.

        """
        return RedisSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    def telegram_settings(self) -> TelegramSettings:
        """Read the bot token and the teachers' ids.

        Returns:
            TelegramSettings - From `TELEGRAM_*`.

        """
        return TelegramSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    def storage_settings(self) -> StorageSettings:
        """Read where files live.

        Returns:
            StorageSettings - From `STORAGE_*`.

        """
        return StorageSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    async def engine(self, settings: DatabaseSettings) -> AsyncIterator[AsyncEngine]:
        """Open the engine.

        Args:
            settings: DatabaseSettings - Database settings.

        Yields:
            AsyncEngine - Engine, disposed on shutdown.

        """
        engine = create_engine(settings)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        """Build the session factory.

        Args:
            engine: AsyncEngine - Engine.

        Returns:
            async_sessionmaker[AsyncSession] - Session factory.

        """
        return create_session_factory(engine)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        """Open the session of one update or task.

        Args:
            factory: async_sessionmaker[AsyncSession] - Session factory.

        Yields:
            AsyncSession - Session, closed when the update or task ends.

        """
        async with factory() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def uow(self, session: AsyncSession) -> UnitOfWork:
        """Bind the transaction boundary to the session.

        Args:
            session: AsyncSession - The session.

        Returns:
            UnitOfWork - Unit of work over it.

        """
        return SqlAlchemyUnitOfWork(session)

    @provide(scope=Scope.REQUEST)
    def audit(self, session: AsyncSession) -> AuditLog:
        """Write audit entries in the session's transaction.

        Args:
            session: AsyncSession - The session.

        Returns:
            AuditLog - Audit log over it.

        """
        return SqlAlchemyAuditLog(session)

    @provide(scope=Scope.APP)
    def file_store(self, settings: StorageSettings) -> FileStore:
        """Give the file store.

        Args:
            settings: StorageSettings - Where and how large.

        Returns:
            FileStore - The store.

        """
        return FileStore(settings.data_dir, settings.max_file_bytes)

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        """Give the clock.

        Returns:
            Clock - The system clock in UTC.

        """
        return SystemClock()
