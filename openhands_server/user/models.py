"""Simple models for user router."""

from datetime import datetime
from uuid import uuid4

from sqlmodel import Field as SQLField, SQLModel

from openhands_server.utils.date_utils import utc_now


# Not needed for now
# class UserScope(Enum):
#    USER = "USER"
#    SUPER_ADMIN = "SUPER_ADMIN"


class UserInfo(SQLModel, table=True):
    """SQL model for storing users."""

    id: str = SQLField(default=lambda: uuid4().hex, primary_key=True)
    name: str | None
    avatar_url: str | None
    language: str | None
    default_llm_model: str | None
    email: str | None
    email_verified: bool = False
    accepted_tos: bool = False

    # Not needed for now
    # user_scopes: list[UserScope] = SQLField(default=list, sa_column=Column(JSON))

    created_at: datetime = SQLField(default_factory=utc_now)
    created_at: datetime = SQLField(default_factory=utc_now)
