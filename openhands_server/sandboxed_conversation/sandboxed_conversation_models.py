from pydantic import BaseModel, Field

from openhands.agent_server.models import ConversationInfo, StartConversationRequest
from openhands_server.event_callback.event_callback_models import EventCallbackProcessor
from openhands_server.sandbox.sandbox_models import SandboxInfo


class SandboxedConversationInfo(BaseModel):
    conversation_info: ConversationInfo
    sandbox_info: SandboxInfo


class SandboxedConversationPage(BaseModel):
    items: list[SandboxedConversationInfo]
    next_page_id: str | None = None


class StartSandboxedConversationRequest(BaseModel):
    """Although a user can go directly to the sandbox and start conversations, these will lack
    any of the stored settings for a user, and perhaps some of the initial settings related to git.
    Starting a conversation in the managing server allows default parameters / secrets to be loaded from
    settings."""

    sandbox_id: str | None = Field(default=None)
    request: StartConversationRequest  # TODO: Since this may be taken from the default, a lot of these settings need to be made optional.
    processors: list[EventCallbackProcessor]
