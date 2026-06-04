"""Async SQLAlchemy engine and session management.

Supports both SQLite (local dev) and PostgreSQL (Railway/production).

SQLite notes:
- Only one writer at a time; we set timeout so writers wait up to 30s.
- Retry logic for "database is locked" errors.

PostgreSQL notes:
- No lock contention issues; connection pooling via asyncpg.
- Use Railway's DATABASE_URL env var (auto-set when PostgreSQL plugin added).
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL, IS_SQLITE

logger = logging.getLogger(__name__)

# Number of times to retry a write operation on "database is locked"
DB_RETRY_LIMIT = 3
DB_RETRY_DELAY = 0.5  # seconds


async def retry_on_lock(func, *args, **kwargs):
    """Execute func(*args, **kwargs), retrying on SQLite lock errors.

    No-op for PostgreSQL (no lock contention).
    """
    if not IS_SQLITE:
        return await func(*args, **kwargs)

    last_error = None
    for attempt in range(DB_RETRY_LIMIT):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "database is locked" in err_str or "database table is locked" in err_str:
                last_error = e
                logger.warning(f"[db] Lock conflict (attempt {attempt + 1}/{DB_RETRY_LIMIT}), retrying...")
                await asyncio.sleep(DB_RETRY_DELAY * (attempt + 1))
                continue
            raise
    raise last_error


# Create engine — different configs for SQLite vs PostgreSQL
_engine_kwargs = {"echo": False}

if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"timeout": 30}
else:
    # PostgreSQL: connection pooling
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

# Async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables. Call once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[db] Tables created / verified")
