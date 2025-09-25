import json
import os
from pathlib import Path
from unittest.mock import MagicMock

from pydantic import BaseModel, Field

from openhands_server.event.event_context import EventContextFactory
from openhands_server.event_callback.event_callback_context import (
    EventCallbackContextFactory,
)
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContextFactory,
)
from openhands_server.sandbox.sandbox_context import SandboxContextFactory
from openhands_server.sandbox.sandbox_spec_context import SandboxSpecContextFactory
from openhands_server.sandboxed_conversation.sandboxed_conversation_context import (
    SandboxedConversationContextFactory,
)


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_ENTERPRISE_SERVER_CONFIG_PATH"
GCP_REGION = os.environ.get("GCP_REGION")

# Default config file location
DEFAULT_CONFIG_FILE_PATH = "workspace/openhands_enterprise_server_config.json"


def _get_db_url() -> str:
    url = os.environ.get("DB_URL")
    if url:
        return url

    # Legacy fallback
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "openhands")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASS", "postgres")
    if host:
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    # Default to sqlite
    return "sqlite+aiosqlite:///./openhands.db"


def _get_event_context_factory():
    from openhands_server.event.filesystem_event_context import (
        FilesystemEventContextFactory,
    )

    return FilesystemEventContextFactory()


def _get_event_callback_context_factory():
    from openhands_server.event_callback.sqlalchemy_event_callback_context import (
        SQLAlchemyEventCallbackContextFactory,
    )

    return SQLAlchemyEventCallbackContextFactory()


def _get_event_callback_result_context_factory():
    from openhands_server.event_callback import (
        sqlalchemy_event_callback_result_context as ctx,
    )

    return ctx.SQLAlchemyEventCallbackResultContextFactory()


def _get_sandbox_context_factory():
    from openhands_server.sandbox import (
        docker_sandbox_context as ctx,
    )

    return ctx.DockerSandboxContextFactory()


def _get_sandbox_spec_context_factory():
    from openhands_server.sandbox import (
        docker_sandbox_spec_context as ctx,
    )

    return ctx.DockerSandboxSpecContextFactory()


def _get_sandboxed_conversation_context_factory():
    return MagicMock()  # TODO: Replace with real!


class GCPConfig(BaseModel):
    project: str | None = os.getenv("GCP_PROJECT")
    region: str | None = os.getenv("GCP_REGION")


class DatabaseConfig(BaseModel):
    """Configuration specific to the database"""

    url: str = _get_db_url()
    name: str | None = os.getenv("DB_NAME")
    user: str | None = os.getenv("DB_USER")
    password: str | None = os.getenv("DB_PASSWORD")
    echo: bool = False
    gcp_db_instance: str | None = os.getenv("GCP_DB_INSTANCE")
    pool_size: int = int(os.environ.get("DB_POOL_SIZE", "25"))
    max_overflow: int = int(os.environ.get("DB_MAX_OVERFLOW", "10"))


class OpenHandsServerConfig(BaseModel):
    event_context_factory: EventContextFactory = Field(
        default_factory=_get_event_context_factory
    )
    event_callback_context_factory: EventCallbackContextFactory = Field(
        default_factory=_get_event_callback_context_factory
    )
    event_callback_result_context_factory: EventCallbackResultContextFactory = Field(
        default_factory=_get_event_callback_result_context_factory
    )
    sandbox_context_factory: SandboxContextFactory = Field(
        default_factory=_get_sandbox_context_factory
    )
    sandbox_spec_context_factory: SandboxSpecContextFactory = Field(
        default_factory=_get_sandbox_spec_context_factory
    )
    sandboxed_conversation_context_factory: SandboxedConversationContextFactory = Field(
        default_factory=_get_sandboxed_conversation_context_factory
    )

    allow_cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Set of CORS origins permitted by this server (Anything from localhost is "
            "always accepted regardless of what's in here)."
        ),
    )
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    gcp: GCPConfig = Field(default_factory=GCPConfig)


_global_config: OpenHandsServerConfig | None = None


def get_global_config() -> OpenHandsServerConfig:
    """Get the default local server config shared across the server"""
    global _global_config
    if _global_config is None:
        # Get config file path from environment variable or use default
        config_file_path = os.getenv(CONFIG_FILE_PATH_ENV, DEFAULT_CONFIG_FILE_PATH)
        config_path = Path(config_file_path)

        # Load configuration from JSON file
        if config_path.exists():
            print(f"⚙️  Loading OpenHands Enterprise Server Config from {config_path}")
            _global_config = OpenHandsServerConfig.model_validate_json(
                json.loads(config_path.read_text())
            )
        else:
            print("⚙️  Using Default OpenHands Enterprise Server Config")
            _global_config = OpenHandsServerConfig()

    return _global_config
