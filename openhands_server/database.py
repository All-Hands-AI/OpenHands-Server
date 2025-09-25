"""Database configuration and session management for OpenHands Server."""

import asyncio
from typing import AsyncGenerator

from fastapi import Request
from google.cloud.sql.connector import Connector
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.util import await_only

from openhands_server.config import get_global_config


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


async def async_creator():
    config = get_global_config()
    loop = asyncio.get_running_loop()
    async with Connector(loop=loop) as connector:
        conn = await connector.connect_async(
            f"{config.gcp.project}:{config.gcp.region}:{config.database.gcp_db_instance}",
            "asyncpg",
            user=config.database.user,
            password=config.database.password,
            db=config.database.name,
        )
        return conn


def _create_async_db_engine():
    config = get_global_config()
    if config.database.gcp_db_instance:  # GCP environments

        def adapted_creator():
            dbapi = engine.dialect.dbapi
            from sqlalchemy.dialects.postgresql.asyncpg import (
                AsyncAdapt_asyncpg_connection,
            )

            return AsyncAdapt_asyncpg_connection(
                dbapi,
                await_only(async_creator()),
                prepared_statement_cache_size=100,
            )

        # create async connection pool with wrapped creator
        return create_async_engine(
            "postgresql+asyncpg://",
            creator=adapted_creator,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_pre_ping=True,
        )
    else:
        return create_async_engine(
            config.database.url,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_pre_ping=True,
        )


# Create async engine
engine = _create_async_db_engine()


# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields database sessions.

    This function creates a new database session for each request
    and ensures it's properly closed after use.

    Yields:
        AsyncSession: An async SQLAlchemy session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def async_session_dependency(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that manages database sessions through request state.

    This function stores the database session in the request state to enable
    session reuse across multiple dependencies within the same request.
    If a session already exists in the request state, it returns that session.
    Otherwise, it creates a new session and stores it in the request state.

    Args:
        request: The FastAPI request object

    Yields:
        AsyncSession: An async SQLAlchemy session stored in request state
    """
    # Check if a session already exists in the request state
    if hasattr(request.state, "db_session"):
        # Return the existing session
        yield request.state.db_session
    else:
        # Create a new session and store it in request state
        async with AsyncSessionLocal() as session:
            try:
                request.state.db_session = session
                yield session
            finally:
                # Clean up the session from request state
                if hasattr(request.state, "db_session"):
                    delattr(request.state, "db_session")
                await session.close()


# TODO: We should delete the two methods below once we have alembic migrations set up


async def create_tables() -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
