from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from openhands_server.utils.date_utils import utc_now


class SandboxStatus(Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ERROR = "ERROR"


class ExposedUrl(BaseModel):
    """URL to access some named service within the container."""

    name: str
    url: str


class SandboxInfo(BaseModel):
    """Information about a sandbox"""

    id: UUID
    user_id: str
    sandbox_spec_id: str
    status: SandboxStatus
    url: str | None = Field(
        description="URL to access sandbox. Sandboxes with a status STARTING / PAUSED / DELETED / ERROR will not have a url"
    )
    session_api_key: SecretStr | None = Field(
        description="Key to access sandbox, to be added as an `X-Session-API-Key` header in each request. Sandboxes with a status STARTING / PAUSED / DELETED / ERROR will not have a key"
    )
    exposed_urls: list[ExposedUrl] = Field(
        default_factory=list,
        description="URLs exposed by the sandbox (App server, Vscode, etc...)",
    )
    created_at: datetime = Field(default_factory=utc_now)


class SandboxPage(BaseModel):
    items: list[SandboxInfo]
    next_page_id: str | None = None
