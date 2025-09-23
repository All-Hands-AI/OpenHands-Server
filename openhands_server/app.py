"""FastAPI application for OpenHands Server."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import conversation, runtime


app = FastAPI(
    title="OpenHands Server",
    description="REST/WebSocket interface for OpenHands AI Agent",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(conversation.router)
app.include_router(runtime.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to OpenHands Server",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }
