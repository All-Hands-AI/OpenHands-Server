"""FastAPI application for OpenHands Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI

from openhands.agent_server.middleware import LocalhostCORSMiddleware

from openhands_server.config import get_default_config
from openhands_server.database import create_tables, drop_tables
from openhands_server.conversation_callback import conversation_callback_router

_config = get_default_config()


@asynccontextmanager
async def _api_lifespan(api: FastAPI) -> AsyncIterator[None]:
    #TODO: Replace this with an invocation of the alembic migrations
    await create_tables()
    yield
    await drop_tables()


api = FastAPI(
    title="OpenHands Enterprise Server",
    description="REST/WebSocket interface for OpenHands AI Agent",
    version="0.1.0",
    lifespan=_api_lifespan
)

# Add CORS middleware
api.add_middleware(LocalhostCORSMiddleware, allow_origins=_config.allow_cors_origins)

# Include routers
api.include_router(conversation_callback_router.router)


@api.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to OpenHands Server",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }
