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
    created_at: datetime = SQLField(default_factory=utc_now, index=True)
    updated_at: datetime = SQLField(default_factory=utc_now, index=True)


class UpdateUserRequest(CreateUserRequest):
    id: str = Field(default_factory=lambda: base62.encodebytes(os.urandom(16)))


class UserSortOrder(Enum):
    EMAIL = "EMAIL"
    EMAIL_DESC = "EMAIL_DESC"
    NAME = "NAME"
    NAME_DESC = "NAME_DESC"
    CREATED_AT = "CREATED_AT"
    CREATED_AT_DESC = "CREATED_AT_DESC"
    UPDATED_AT = "UPDATED_AT"
    UPDATED_AT_DESC = "UPDATED_AT_DESC"


class UserInfoPage(BaseModel):
    items: list[UserInfo]
    next_page_id: str | None = None
