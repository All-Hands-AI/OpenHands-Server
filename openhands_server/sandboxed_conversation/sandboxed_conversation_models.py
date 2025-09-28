from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField, SQLModel

from openhands.sdk.conversation.state import AgentExecutionStatus
from openhands_server.event_callback.event_callback_models import EventCallbackProcessor
from openhands_server.sandbox.sandbox_models import SandboxStatus
from openhands_server.utils.date_utils import utc_now


class StoredConversationInfo(SQLModel):
    id: UUID = SQLField(default=uuid4, primary_key=True)
    title: str | None

    # I'm removing this for now because I am not sure if events include metrics anymore
    # metrics: MetricsSnapshot | None = None

    sandbox_id: str = SQLField(index=True)
    created_at: datetime = SQLField(default_factory=utc_now, index=True)
    updated_at: datetime = SQLField(default_factory=utc_now, index=True)


class SandboxedConversationResponse(StoredConversationInfo):
    sandbox_status: SandboxStatus
    agent_status: AgentExecutionStatus


class SandboxedConversationResponseSortOrder(Enum):
    CREATED_AT = "CREATED_AT"
    CREATED_AT_DESC = "CREATED_AT_DESC"
    UPDATED_AT = "UPDATED_AT"
    UPDATED_AT_DESC = "UPDATED_AT_DESC"
    TITLE = "TITLE"
    TITLE_DESC = "TITLE_DESC"


class SandboxedConversationResponsePage(BaseModel):
    items: list[SandboxedConversationResponse]
    next_page_id: str | None = None


class StartSandboxedConversationRequest(BaseModel):
    """Although a user can go directly to the sandbox and start conversations, these
    will lack any of the stored settings for a user. Starting a conversation in the
    app server allows default parameters / secrets to be loaded from settings."""

    sandbox_id: str | None = Field(default=None)

    # Removed for now - just use value from UserInfo
    # model: str | None = None

    processors: list[EventCallbackProcessor] = Field(default_factory=list)
