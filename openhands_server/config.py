import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_ENTERPRISE_SERVER_CONFIG_PATH"

# Default config file location
DEFAULT_CONFIG_FILE_PATH = "workspace/openhands_enterprise_server_config.json"


class OpenHandsServerConfig(BaseModel):
    auth_context_type: str = Field(
        default="openhands_server.auth.dummy.DummyAuthContext",
        description="The class to use for AuthContext dependencies",
    )
    sandbox_spec_context_type: str = Field(
        default="openhands_server.sandbox_spec.docker_sandbox_spec_context.DockerSandboxSpecContext",
        description="The class to use for SandboxSpecContext dependencies",
    )
    sandbox_context_type: str = Field(
        default="openhands_server.sandbox.docker_sandbox_context.DockerSandboxContext",
        description="The class to use for SandboxContext dependencies",
    )
    conversation_callback_context_type: str = Field(
        default="openhands_server.conversation_callback.sqlalchemy_conversation_callback_context.SQLAlchemyConversationCallbackContext",
        description="The class to use for ConversationCallbackContext dependencies",
    )
    sandboxed_conversation_context_type: str = Field(
        default="openhands_server.auth.dummy.DummyAuthContext",
        description="The class to use for SandboxedConversationContext dependencies",
    )


_default_config: OpenHandsServerConfig | None = None


def get_default_config() -> OpenHandsServerConfig:
    """Get the default local server config shared across the server"""
    global _default_config
    if _default_config is None:
        # Get config file path from environment variable or use default
        config_file_path = os.getenv(CONFIG_FILE_PATH_ENV, DEFAULT_CONFIG_FILE_PATH)
        config_path = Path(config_file_path)

        # Load configuration from JSON file with environment variable overrides
        _default_config = OpenHandsServerConfig.model_validate_json(
            json.loads(config_path.read_text())
        )
    return _default_config
