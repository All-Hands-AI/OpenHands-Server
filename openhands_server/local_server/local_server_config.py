from pathlib import Path
from pydantic import BaseModel, Field


class LocalServerConfig(BaseModel):
    """Immutable configuration for a server running in local mode. (Typically inside a sandbox)."""

    session_api_key: str | None = Field(
        default=None,
        description="The session api key used to authenticate all incoming requests. None implies the server will be unsecured",
    )
    local_conversation_service: str = Field(
        default="openhands_server.local_conversation.default_local_conversation_service.DefaultLocalConversationService",
        description="The type of conversation service to use",
    )
    allow_cors_origins: set[str] = Field(
        default_factory=set,
        description="Set of CORS origins permitted by this server. (Default empty set only accepts anything from localhost)",
    )
    conversations_path: Path = Field(
        default=Path("workspace/project"),
        description="The location of the workspace directory where files the agent reads from / writes to in the local file system"
    )
    workspace_path: Path = Field(
        default=Path("workspace/conversations"),
        description="The location of the directory where conversations and events are stored in the local file system"
    )
    model_config = {"frozen": True}


_default_local_server_config: LocalServerConfig | None = None


def get_default_local_server_config():
    """Get the default local server config shared across the server"""
    global _default_local_server_config
    if _default_local_server_config is None:
        _default_local_server_config = LocalServerConfig()
    return _default_local_server_config
