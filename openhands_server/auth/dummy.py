from dataclasses import dataclass
from uuid import UUID

from openhands_server.auth.auth_context import AuthContext
from openhands_server.auth.auth_models import StoreUserSettingsRequest, UserSettings


@dataclass
class DummyAuthContext(AuthContext):
    """Dummy User context used for testing"""

    user_id: str = UUID("00000000-0000-0000-0000-000000000001").hex

    async def load_user_settings(self) -> UserSettings:
        """Load settings for the user"""
        raise NotImplementedError()

    async def store_user_settings(
        self, settings: StoreUserSettingsRequest
    ) -> UserSettings:
        """Store settings for the user"""
        raise NotImplementedError()

    @classmethod
    def get_instance(cls):
        return DummyAuthContext()
