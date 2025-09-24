from abc import ABC, abstractmethod
from typing import Type
from uuid import UUID

from fastapi import Request

from openhands_server.auth.auth_models import AuthType
from openhands_server.config import get_default_config
from openhands_server.utils.import_utils import get_impl


class AuthContext(ABC):
    """Object for providing user access"""

    user_id: UUID
    auth_type: AuthType

    # TODO: Implement this as needed

    # async def load_settings():
    #    """ Load settings for the user """

    # async def store_settings():
    #    """ Store settings for the user """

    # async def load_secrets():
    #    """ Load secrets for the user """

    # async def store_secrets():
    #    """ Store secrets for the user """

    @classmethod
    @abstractmethod
    async def get_instance(cls, request: Request) -> "AuthContext":
        """Get an instance of the auth context for the current request"""


_auth_context_type: Type[AuthContext] | None = None


async def get_auth_context(request: Request) -> AuthContext:
    global _auth_context_type
    if not _auth_context_type:
        config = get_default_config()
        _auth_context_type = get_impl(AuthContext, config.auth_context_type)
    return await _auth_context_type.get_instance(request)
