from abc import ABC
from enum import Enum
from uuid import UUID

from openhands_server.user.user_models import AuthType


class ProviderType(Enum):
    GITHUB = "GITHUB"
    # GITLAB = 'GITLAB'
    # BITBUCKET = 'BITBUCKET'
    # SLACK = 'SLACK'


class ProviderToken(ABC):
    provider_type: ProviderType


class UserContext(ABC):
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
