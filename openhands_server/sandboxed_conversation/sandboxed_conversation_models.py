from pydantic import BaseModel, Field

from openhands.agent_server.models import ConversationInfo, StartConversationRequest
from openhands_server.sandbox.sandbox_models import SandboxInfo


class SandboxedConversationInfo(BaseModel):
    conversation_info: ConversationInfo
    sandbox_info: SandboxInfo


class SandboxedConversationPage(BaseModel):
    items: list[SandboxedConversationInfo]
    next_page_id: str | None = None


class StartSandboxedConversationRequest(BaseModel):
    sandbox_id: str | None = Field(default=None)
    request: StartConversationRequest
    callbacks: list[ConversationCallback]
