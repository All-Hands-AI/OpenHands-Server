"""Database configuration and session management for OpenHands Server."""

import os
from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./openhands.db")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
    future=True,
)

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


async def async_session_dependency(request: Request) -> AsyncGenerator[AsyncSession, None]:
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


async def create_tables() -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Example usage of the async session maker
async def example_usage() -> None:
    """
    Example of how to use the async session maker.

    This function demonstrates the proper way to use async sessions
    for database operations.
    """
    # Method 1: Using the dependency function (recommended for FastAPI)
    async for session in get_async_session():
        # Your database operations here
        # result = await session.execute(select(SomeModel))
        # await session.commit()
        pass

    # Method 2: Using the request-scoped session dependency (for FastAPI with request state)
    # This would be used in FastAPI route handlers like:
    # @app.get("/example")
    # async def example_route(
    #     request: Request,
    #     session: AsyncSession = Depends(async_session_dependency)
    # ):
    #     # Your database operations here
    #     # result = await session.execute(select(SomeModel))
    #     # await session.commit()
    #     pass

    # Method 3: Direct usage with context manager
    async with AsyncSessionLocal() as session:
        try:
            # Your database operations here
            # result = await session.execute(select(SomeModel))
            # await session.commit()
            pass
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
