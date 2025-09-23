from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from openhands_server.local_conversation.local_conversation_event_router import (
    router as local_conversation_event_router,
)
from openhands_server.local_conversation.local_conversation_router import (
    router as local_conversation_router,
)
from openhands_server.local_conversation.local_conversation_service import (
    get_default_local_conversation_service,
)
from openhands_server.local_server.local_server_config import (
    get_default_local_server_config,
)
from openhands_server.utils.middleware import (
    CacheControlMiddleware,
    LocalhostCORSMiddleware,
    ValidateSessionAPIKeyMiddleware,
)


@asynccontextmanager
async def api_lifespan(api: FastAPI) -> AsyncIterator[None]:
    service = get_default_local_conversation_service()
    async with service:
        yield


api = FastAPI(description="OpenHands Local Server", lifespan=api_lifespan)
local_server_config = get_default_local_server_config()


# Add routers
api.include_router(local_conversation_event_router)
api.include_router(local_conversation_router)

# Add middleware
api.add_middleware(LocalhostCORSMiddleware, local_server_config.allow_cors_origins)
api.add_middleware(CacheControlMiddleware)
if local_server_config.session_api_key:
    api.add_middleware(
        ValidateSessionAPIKeyMiddleware, local_server_config.session_api_key
    )
