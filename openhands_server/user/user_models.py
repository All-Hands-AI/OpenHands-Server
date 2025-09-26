from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from openhands_server.utils.date_utils import utc_now


class UserScope(Enum):
    USER = "user"
    """ Regular user """
    SUPER_ADMIN = "superadmin"
    """ Super user - have access to options not available to regular users. """


class CreateUserRequest(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    default_llm_model: str | None = None
    email: str | None
    accepted_tos: bool = False
    user_scopes: list[UserScope] = Field(default_factory=list)


class UpdateUserRequest(CreateUserRequest):
    id: str = Field(default_factory=lambda: uuid4().hex)


class UserInfo(UpdateUserRequest):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserInfoPage:
    items: list[UserInfo]
    next_page_id: str | None = None
