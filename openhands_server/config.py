import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr

from openhands.sdk.utils.models import OpenHandsModel
from openhands_server.event.event_context import EventContextResolver
from openhands_server.event_callback.event_callback_context import (
    EventCallbackContextResolver,
)
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContextResolver,
)
from openhands_server.sandbox.sandbox_context import SandboxContextResolver
from openhands_server.sandbox.sandbox_spec_context import SandboxSpecContextResolver
from openhands_server.sandboxed_conversation.sandboxed_conversation_context import (
    SandboxedConversationContextResolver,
)
from openhands_server.user.user_context import UserContextResolver


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_APP_SERVER_CONFIG_PATH"
GCP_REGION = os.environ.get("GCP_REGION")

# Default config file location
DEFAULT_CONFIG_FILE_PATH = "workspace/openhands_app_server_config.json"


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


class EncryptionKey(BaseModel):
    """Configuration for an encryption key."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    key: SecretStr
    active: bool = True
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


def _get_default_encryption_keys() -> list[EncryptionKey]:
    """Generate default encryption keys."""
    master_key = (
        os.getenv("JWT_SECRET") or os.getenv("MASTER_KEY") or os.urandom(32).hex()
    )
    return [
        EncryptionKey(
            key=SecretStr(master_key),
            active=True,
            notes="Default master key",
        )
    ]


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


class AppServerConfig(OpenHandsModel):
    encryption_keys: list[EncryptionKey] = Field(
        default_factory=_get_default_encryption_keys
    )
    event: EventContextResolver | None = None
    event_callback: EventCallbackContextResolver | None = None
    event_callback_result: EventCallbackResultContextResolver | None = None
    sandbox: SandboxContextResolver | None = None
    sandbox_spec: SandboxSpecContextResolver | None = None
    sandboxed_conversation: SandboxedConversationContextResolver | None = None
    user: UserContextResolver | None = None
    allow_cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Set of CORS origins permitted by this server (Anything from localhost is "
            "always accepted regardless of what's in here)."
        ),
    )
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    gcp: GCPConfig = Field(default_factory=GCPConfig)


_global_config: AppServerConfig | None = None


def get_global_config() -> AppServerConfig:
    """Get the default local server config shared across the server"""
    global _global_config
    if _global_config is None:
        # Get config file path from environment variable or use default
        config_file_path = os.getenv(CONFIG_FILE_PATH_ENV, DEFAULT_CONFIG_FILE_PATH)
        config_path = Path(config_file_path)

        # Load configuration from JSON file
        try:
            if config_path.exists():
                print(f"⚙️  Loading OpenHands App Server Config from {config_path}")
                _global_config = AppServerConfig.model_validate_json(
                    config_path.read_text()
                )
                return _global_config
        except Exception as exc:
            print(f"⚠️  Error OpenHands App Server Config: {exc}")

        print("⚙️  Generating Default OpenHands App Server Config")
        _global_config = AppServerConfig()

        # Save the config because the encryption keys are required between restarts
        # We need to explicitly include secret values for persistence
        config_dict = _global_config.model_dump(mode="json", exclude_defaults=True)
        # Manually include the secret values for the encryption keys
        config_dict["encryption_keys"] = [
            {**key_dict, "key": key.key.get_secret_value()}
            for key, key_dict in zip(
                _global_config.encryption_keys, config_dict["encryption_keys"]
            )
        ]
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config_dict, indent=2))

    return _global_config
