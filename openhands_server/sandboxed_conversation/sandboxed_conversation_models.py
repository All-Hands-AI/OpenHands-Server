

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from openhands_server.local_conversation.agent_info import AgentInfo
from openhands_server.local_conversation.local_conversation_models import LocalConversationInfo


class SandboxedConversationInfo(LocalConversationInfo):
    """Information about a conversation running remotely in a Runtime sandbox """
    sandbox_id: UUID | None


class SandboxedConversationPage(BaseModel):
    items: list[SandboxedConversationInfo]
    next_page_id: str | None = None
