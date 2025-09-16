from pathlib import Path

from pydantic import BaseModel, Field


# TODO: Add a unit test to make sure this class does not import anything from
#       openhands_server to prevent circular imports


class Config(BaseModel):
    """
    Immutable configuration for a server running in local mode.
    (Typically inside a sandbox).
    """

    session_api_key: str | None = Field(
        default=None,
        description=(
            "The session api key used to authenticate all incoming requests. "
            "None implies the server will be unsecured"
        ),
    )
    allow_cors_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Set of CORS origins permitted by this server (Anything from localhost is "
            "always accepted regardless of what's in here)."
        ),
    )
    conversations_path: Path = Field(
        default=Path("workspace/conversations"),
        description=(
            "The location of the directory where conversations and events are stored."
        ),
    )
    workspace_path: Path = Field(
        default=Path("workspace/project"),
        description=(
            "The location of the workspace directory where the agent reads/writes."
        ),
    )
    model_config = {"frozen": True}


_default_config: Config | None = None


def get_default_config():
    """Get the default local server config shared across the server"""
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config
