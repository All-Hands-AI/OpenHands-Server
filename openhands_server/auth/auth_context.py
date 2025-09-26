from abc import ABC, abstractmethod
from typing import AsyncGenerator
from uuid import UUID

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.auth.auth_models import StoreUserSettingsRequest, UserSettings


class AuthContext(ABC):
    """Object for providing user access"""

    user_id: UUID

    @abstractmethod
    async def load_settings(self) -> UserSettings:
        """Load settings for the user"""
        raise NotImplementedError()

    @abstractmethod
    async def store_settings(self, settings: StoreUserSettingsRequest) -> UserSettings:
        """Store settings for the user"""
        raise NotImplementedError()

    # async def load_secrets():
    #    """ Load secrets for the user """

    # async def store_secrets():
    #    """ Store secrets for the user """

    async def __aenter__(self) -> "AuthContext":
        """Start using this service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this service"""


class AuthContextResolver(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def with_instance(
        self, *args, **kwargs
    ) -> AsyncGenerator["AuthContext", None]:
        """
        Get an instance of auth context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables.
        """
        yield AuthContext()  # type: ignore
