"""SQLAlchemy implementation of EventCallbackContext."""

from __future__ import annotations

from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.database import async_session_dependency
from openhands_server.event_callback.event_callback_context import EventCallbackContext
from openhands_server.event_callback.event_callback_db_models import StoredEventCallback
from openhands_server.event_callback.event_callback_models import (
    CreateEventCallbackRequest,
    EventCallback,
    EventCallbackPage,
    EventKind,
)


class SQLAlchemyEventCallbackContext(EventCallbackContext):
    """SQLAlchemy implementation of EventCallbackContext."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the SQLAlchemy event callback context.

        Args:
            session: The async SQLAlchemy session
        """
        self.session = session

    async def create_event_callback(
        self, request: CreateEventCallbackRequest
    ) -> EventCallback:
        """Create a new event callback."""
        # Create EventCallback from request
        event_callback = EventCallback(
            conversation_id=request.conversation_id,
            processor=request.processor,
            event_kind=request.event_kind,
        )

        # Convert to database model
        stored_callback = StoredEventCallback.from_pydantic(event_callback)

        # Add to session and commit
        self.session.add(stored_callback)
        await self.session.commit()
        await self.session.refresh(stored_callback)

        # Return the Pydantic model
        return stored_callback.to_pydantic()

    async def get_event_callback(self, id: UUID) -> EventCallback | None:
        """Get a single event callback, returning None if not found."""
        stmt = select(StoredEventCallback).where(StoredEventCallback.id == id)
        result = await self.session.execute(stmt)
        stored_callback = result.scalar_one_or_none()

        if stored_callback is None:
            return None

        return stored_callback.to_pydantic()

    async def delete_event_callback(self, id: UUID) -> bool:
        """Delete an event callback, returning True if deleted, False if not found."""
        stmt = select(StoredEventCallback).where(StoredEventCallback.id == id)
        result = await self.session.execute(stmt)
        stored_callback = result.scalar_one_or_none()

        if stored_callback is None:
            return False

        await self.session.delete(stored_callback)
        await self.session.commit()
        return True

    async def search_event_callbacks(
        self,
        conversation_id__eq: UUID | None = None,
        event_kind__eq: EventKind | None = None,
        event_id__eq: UUID | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventCallbackPage:
        """Search for event callbacks, optionally filtered by parameters."""
        # Build the query with filters
        conditions = []

        if conversation_id__eq is not None:
            conditions.append(
                StoredEventCallback.conversation_id == conversation_id__eq
            )

        if event_kind__eq is not None:
            conditions.append(StoredEventCallback.event_kind == event_kind__eq)

        # Note: event_id__eq is not stored in the event_callbacks table
        # This parameter might be used for filtering results after retrieval
        # or might be intended for a different use case

        # Build the base query
        stmt = select(StoredEventCallback)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Handle pagination
        if page_id is not None:
            # Parse page_id to get offset or cursor
            try:
                offset = int(page_id)
                stmt = stmt.offset(offset)
            except ValueError:
                # If page_id is not a valid integer, start from beginning
                offset = 0
        else:
            offset = 0

        # Apply limit and get one extra to check if there are more results
        stmt = stmt.limit(limit + 1).order_by(StoredEventCallback.created_at.desc())

        result = await self.session.execute(stmt)
        stored_callbacks = result.scalars().all()

        # Check if there are more results
        has_more = len(stored_callbacks) > limit
        if has_more:
            stored_callbacks = stored_callbacks[:limit]

        # Convert to Pydantic models
        items = [callback.to_pydantic() for callback in stored_callbacks]

        # Calculate next page ID
        next_page_id = None
        if has_more:
            next_page_id = str(offset + limit)

        return EventCallbackPage(items=items, next_page_id=next_page_id)

    @classmethod
    async def with_instance(  # type: ignore[override]
        cls,
        session: AsyncSession = Depends(async_session_dependency),
    ) -> AsyncGenerator["SQLAlchemyEventCallbackContext", None]:
        """
        Get an instance of SQLAlchemy event callback context.

        Args:
            session: The async SQLAlchemy session from dependency injection

        Yields:
            SQLAlchemyEventCallbackContext: The context instance
        """
        context = cls(session)
        try:
            yield context
        finally:
            # Session cleanup is handled by the dependency
            pass
