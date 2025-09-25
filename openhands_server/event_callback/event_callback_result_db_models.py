"""SQLAlchemy database models for event callback results."""

from __future__ import annotations

import uuid

from sqlalchemy import UUID, Column, DateTime, String, Text
from sqlalchemy.ext.hybrid import hybrid_property

from openhands_server.database import Base
from openhands_server.event_callback.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultStatus,
)
from openhands_server.utils.date_utils import utc_now


class StoredEventCallbackResult(Base):
    """SQLAlchemy model for storing event callback results."""

    __tablename__ = "event_callback_results"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    status = Column(String, nullable=False, index=True)
    event_callback_id = Column(UUID, nullable=False, index=True)
    event_id = Column(String, nullable=False, index=True)
    conversation_id = Column(UUID, nullable=False, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    @hybrid_property
    def status_enum(self) -> EventCallbackResultStatus:
        """
        Get the status as an enum.

        Returns:
            EventCallbackResultStatus: The status enum value
        """
        return EventCallbackResultStatus(self.status)

    @status_enum.setter
    def set_status_enum(self, value: EventCallbackResultStatus) -> None:
        """
        Set the status from an enum.

        Args:
            value: The status enum value to set
        """
        self.status = value.value

    def to_pydantic(self) -> EventCallbackResult:
        """
        Convert the SQLAlchemy model to a Pydantic model.

        Returns:
            EventCallbackResult: The Pydantic model representation
        """
        return EventCallbackResult(
            id=self.id,  # type: ignore[arg-type]
            status=self.status_enum,
            event_callback_id=self.event_callback_id,  # type: ignore[arg-type]
            event_id=self.event_id,  # type: ignore[arg-type]
            conversation_id=self.conversation_id,  # type: ignore[arg-type]
            detail=self.detail,  # type: ignore[arg-type]
            created_at=self.created_at,  # type: ignore[arg-type]
        )

    @classmethod
    def from_pydantic(cls, result: EventCallbackResult) -> StoredEventCallbackResult:
        """
        Create a SQLAlchemy model from a Pydantic model.

        Args:
            result: The Pydantic EventCallbackResult model

        Returns:
            StoredEventCallbackResult: The SQLAlchemy model instance
        """
        return cls(
            id=result.id,
            status=result.status.value,
            event_callback_id=result.event_callback_id,
            event_id=result.event_id,
            conversation_id=result.conversation_id,
            detail=result.detail,
            created_at=result.created_at,
        )
