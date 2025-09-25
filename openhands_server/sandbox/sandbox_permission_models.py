from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from openhands_server.utils.date_utils import utc_now


class SandboxPermission(BaseModel):
    """Permission model for sandbox. Conversation permissions are handled at the sandbox level.
    (Since once a user has access to the session_api_key, enforcing further constraints is impossilbe)"""

    sandbox_id: UUID
    user_id: UUID
    created_by_user_id: UUID | None = None
    full_access: bool = Field(
        default=False,
        description="Indicates that a user has full access to sandbox session_api_key.",
    )
    timestamp: datetime = Field(default_factory=utc_now)


class SandboxPermissionPage(BaseModel):
    items: list[SandboxPermission]
    next_page_id: str | None = None
