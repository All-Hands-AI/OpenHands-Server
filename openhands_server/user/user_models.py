import os
from datetime import datetime
from enum import Enum
from uuid import uuid4

import base62
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField

from openhands_server.utils.date_utils import utc_now


class UserScope(Enum):
    USER = "USER"
    """ Regular user """
    SUPER_ADMIN = "SUPER_ADMIN"
    """ Super user - have access to options not available to regular users. """


class CreateUserRequest(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    default_llm_model: str | None = None
    email: str | None
    accepted_tos: bool = False
    user_scopes: list[UserScope] = SQLField(
        default_factory=list, sa_column=Column(JSON)
    )


class UserInfo(CreateUserRequest, table=True):
    """SQL model for storing users."""

    id: str = SQLField(default=lambda: uuid4().hex, primary_key=True)
    email_verified: bool = False
    created_at: datetime = SQLField(default_factory=utc_now)
    updated_at: datetime = SQLField(default_factory=utc_now)


class UpdateUserRequest(CreateUserRequest):
    id: str = Field(default_factory=lambda: base62.encodebytes(os.urandom(16)))


class UserInfoPage(BaseModel):
    items: list[UserInfo]
    next_page_id: str | None = None
