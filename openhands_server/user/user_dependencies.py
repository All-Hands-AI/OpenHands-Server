from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request

from openhands_server.user.user_context import UserContext
from openhands_server.user.user_models import AuthType


# TODO: Implement this correctly to match https://github.com/All-Hands-AI/OpenHands/issues/10850


@dataclass
class _DummyUserContext(UserContext):
    """Dummy User context used for testing"""

    user_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    auth_type: AuthType = AuthType.BEARER


async def get_user_context(request: Request) -> UserContext:
    """Dependency to get the current user context from the request"""
    user_context = request.state.get("user_context")
    if user_context:
        return user_context

    # TODO: This is just for testing. Implement this properly
    user_context = _DummyUserContext()

    # Cache parameter in request and return
    request.state["user_context"] = user_context
    return user_context


async def get_user_id(user_context: UserContext = Depends(get_user_context)) -> UUID:
    return user_context.user_id
