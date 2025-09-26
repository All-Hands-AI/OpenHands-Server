from datetime import datetime

from pydantic import BaseModel, Field

from openhands_server.utils.date_utils import utc_now


class StoreUserSettingsRequest(BaseModel):
    language: str | None = None
    confirmation_mode: bool = False
    default_llm_model: str | None = None
    email: str | None


class UserSettings(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
