from dataclasses import dataclass
from uuid import UUID

from openhands_server.auth.auth_context import AuthContext
from openhands_server.auth.auth_models import AuthType


@dataclass
class DummyAuthContext(AuthContext):
    """Dummy User context used for testing"""

    user_id: UUID = UUID("00000000-0000-0000-0000-000000000000")
    auth_type: AuthType = AuthType.BEARER

    @classmethod
    def get_instance(cls):
        return DummyAuthContext()
