from enum import Enum


class AuthType(Enum):
    """Authentication type for user context"""

    BEARER = "BEARER"
    API_KEY = "API_KEY"
    OAUTH = "OAUTH"
