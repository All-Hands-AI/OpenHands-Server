from typing import Sequence
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class LocalhostCORSMiddleware(CORSMiddleware):
    """Custom CORS middleware that allows any request from localhost/127.0.0.1 domains,
    while using standard CORS rules for other origins.
    """

    def __init__(self, app: ASGIApp, allow_origins: Sequence[str]) -> None:
        super().__init__(
            app,
            allow_origins=allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def is_allowed_origin(self, origin: str) -> bool:
        if origin and not self.allow_origins and not self.allow_origin_regex:
            parsed = urlparse(origin)
            hostname = parsed.hostname or ""

            # Allow any localhost/127.0.0.1 origin regardless of port
            if hostname in ["localhost", "127.0.0.1"]:
                return True

        # For missing origin or other origins, use the parent class's logic
        result: bool = super().is_allowed_origin(origin)
        return result


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Middleware to disable caching for all routes by adding appropriate headers"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/assets"):
            # The content of the assets directory has fingerprinted file names so we cache aggressively
            response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
        else:
            response.headers["Cache-Control"] = (
                "no-cache, no-store, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


class ValidateSessionAPIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to disable caching for all routes by adding appropriate headers"""

    def __init__(self, app: ASGIApp, session_api_key: str) -> None:
        super().__init__(app)
        self.session_api_key = session_api_key

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        session_api_key = request.headers["X-Session-API-Key"]
        if session_api_key != session_api_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED)
        response = await call_next(request)
        return response
