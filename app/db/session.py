from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str, *, pool_size: int = 5, max_overflow: int = 10) -> None:
    global _engine, _session_maker
    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
    )
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() at startup.")
    return _session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
