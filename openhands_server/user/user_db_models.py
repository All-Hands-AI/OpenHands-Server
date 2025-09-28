"""SQL database models for users."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, String

from openhands_server.database import Base
from openhands_server.user.user_models import UserInfo, UserScope
from openhands_server.utils.date_utils import utc_now


class StoredUser(Base):
    """SQL model for storing users."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    language = Column(String, nullable=True)
    default_llm_model = Column(String, nullable=True)
    email = Column(String, nullable=True)
    accepted_tos = Column(Boolean, nullable=False, default=False)
    user_scopes = Column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )

    def to_pydantic(self) -> UserInfo:
        """
        Convert the SQL model to a Pydantic model.

        Returns:
            UserInfo: The Pydantic representation of the user
        """
        return UserInfo(
            id=self.id,  # type: ignore[arg-type]
            name=self.name,  # type: ignore[arg-type]
            avatar_url=self.avatar_url,  # type: ignore[arg-type]
            language=self.language,  # type: ignore[arg-type]
            default_llm_model=self.default_llm_model,  # type: ignore[arg-type]
            email=self.email,  # type: ignore[arg-type]
            accepted_tos=self.accepted_tos,  # type: ignore[arg-type]
            user_scopes=[UserScope(scope) for scope in (self.user_scopes or [])],  # type: ignore[arg-type]
            created_at=self.created_at,  # type: ignore[arg-type]
            updated_at=self.updated_at,  # type: ignore[arg-type]
        )

    @classmethod
    def from_pydantic(cls, user_info: UserInfo) -> "StoredUser":
        """
        Create a SQL model from a Pydantic model.

        Args:
            user_info: The Pydantic user info model

        Returns:
            StoredUser: The SQL representation
        """
        return cls(
            id=user_info.id,
            name=user_info.name,
            avatar_url=user_info.avatar_url,
            language=user_info.language,
            default_llm_model=user_info.default_llm_model,
            email=user_info.email,
            accepted_tos=user_info.accepted_tos,
            user_scopes=[scope.value for scope in user_info.user_scopes],
            created_at=user_info.created_at,
            updated_at=user_info.updated_at,
        )
