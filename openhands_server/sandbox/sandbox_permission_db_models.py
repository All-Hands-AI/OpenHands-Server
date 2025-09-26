"""SQLAlchemy database models for sandbox permissions."""

from __future__ import annotations

import uuid

from sqlalchemy import UUID, Boolean, Column, DateTime, String

from openhands_server.database import Base
from openhands_server.sandbox.sandbox_permission_models import SandboxPermission
from openhands_server.utils.date_utils import utc_now


class StoredSandboxPermission(Base):
    """SQLAlchemy model for storing sandbox permissions."""

    __tablename__ = "sandbox_permissions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    sandbox_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    created_by_user_id = Column(String, nullable=True)
    full_access = Column(Boolean, nullable=False, default=False)
    timestamp = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    def to_pydantic(self) -> SandboxPermission:
        """
        Convert the SQLAlchemy model to a Pydantic model.

        Returns:
            SandboxPermission: The Pydantic representation of the sandbox permission
        """
        return SandboxPermission(
            id=self.id,  # type: ignore
            sandbox_id=self.sandbox_id,  # type: ignore
            user_id=self.user_id,  # type: ignore
            created_by_user_id=self.created_by_user_id,  # type: ignore
            full_access=self.full_access,  # type: ignore
            timestamp=self.timestamp,  # type: ignore
        )

    @classmethod
    def from_pydantic(
        cls, sandbox_permission: SandboxPermission
    ) -> "StoredSandboxPermission":
        """
        Create a SQLAlchemy model from a Pydantic model.

        Args:
            sandbox_permission: The Pydantic sandbox permission model

        Returns:
            StoredSandboxPermission: The SQLAlchemy representation
        """
        return cls(
            id=sandbox_permission.id,
            sandbox_id=sandbox_permission.sandbox_id,
            user_id=sandbox_permission.user_id,
            created_by_user_id=sandbox_permission.created_by_user_id,
            full_access=sandbox_permission.full_access,
            timestamp=sandbox_permission.timestamp,
        )
