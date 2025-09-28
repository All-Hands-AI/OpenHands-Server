from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from openhands_server.utils.date_utils import utc_now


class SandboxPermission(SQLModel):
    """Permission model for sandbox. Conversation permissions are handled at the sandbox
    level. (Since once a user has access to the session_api_key, enforcing further
    constraints is impossilbe)"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sandbox_id: str = Field(index=True)
    user_id: str = Field(index=True)
    created_by_user_id: str | None = Field(index=True)
    full_access: bool = Field(
        default=False,
        description="Indicates that a user has full access to sandbox session_api_key.",
    )
    timestamp: datetime = Field(default_factory=utc_now, index=True)


class SandboxPermissionPage(BaseModel):
    items: list[SandboxPermission]
    next_page_id: str | None = None
