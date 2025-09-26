from abc import ABC, abstractmethod
from typing import Callable

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.auth.auth_models import StoreUserSettingsRequest, UserSettings


class AuthContext(ABC):
    """Object for providing user access"""

    user_id: str

    @abstractmethod
    async def load_user_settings(self) -> UserSettings:
        """Load settings for the user"""
        raise NotImplementedError()

    @abstractmethod
    async def store_user_settings(
        self, settings: StoreUserSettingsRequest
    ) -> UserSettings:
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
    def get_resolver(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of auth context.
        """
