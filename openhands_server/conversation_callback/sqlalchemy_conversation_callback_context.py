"""SQLAlchemy implementation of ConversationCallbackContext."""

from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.conversation_callback.conversation_callback_context import (
    ConversationCallbackContext,
)
from openhands_server.conversation_callback.conversation_callback_database_models import (
    StoredConversationCallback,
)
from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackPage,
    ConversationCallbackStatus,
)
from openhands_server.database import async_session_dependency


class SQLAlchemyConversationCallbackContext(ConversationCallbackContext):
    """SQLAlchemy implementation of ConversationCallbackContext."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the context with a database session.

        Args:
            session: The SQLAlchemy async session
        """
        self.session = session

    @classmethod
    async def get_instance(
        cls, session: AsyncSession = Depends(async_session_dependency)
    ) -> "SQLAlchemyConversationCallbackContext":
        """
        Get an instance of the SQLAlchemy conversation callback context.

        Returns:
            SQLAlchemyConversationCallbackContext: The context instance
        """
        return cls(session)

    async def search_conversation_callbacks(
        self,
        conversation_id: UUID | None = None,
        status: ConversationCallbackStatus | None = None,
        event_kind: str | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> ConversationCallbackPage:
        """
        Search for conversation callbacks with optional filters.

        Args:
            conversation_id: Optional conversation ID filter
            status: Optional status filter
            event_kind: Optional event kind filter
            page_id: Optional page ID for pagination (UUID string)
            limit: Maximum number of results to return

        Returns:
            ConversationCallbackPage: Page of conversation callbacks
        """
        query = select(StoredConversationCallback)

        # Apply filters
        conditions = []
        if conversation_id is not None:
            conditions.append(
                StoredConversationCallback.conversation_id == conversation_id
            )
        if status is not None:
            conditions.append(StoredConversationCallback.status == status.value)
        if event_kind is not None:
            conditions.append(StoredConversationCallback.event_kind == event_kind)

        if conditions:
            query = query.where(and_(*conditions))

        # Apply pagination
        if page_id:
            try:
                page_uuid = UUID(page_id)
                query = query.where(StoredConversationCallback.id < page_uuid)
            except ValueError:
                # Invalid UUID, ignore pagination
                pass

        # Order by ID descending for consistent pagination
        query = query.order_by(desc(StoredConversationCallback.id)).limit(limit + 1)

        result = await self.session.execute(query)
        stored_callbacks = result.scalars().all()

        # Convert to Pydantic models
        callbacks = [callback.to_pydantic() for callback in stored_callbacks[:limit]]

        # Determine next page ID
        next_page_id = None
        if len(stored_callbacks) > limit:
            next_page_id = str(stored_callbacks[limit - 1].id)

        return ConversationCallbackPage(
            items=callbacks,
            next_page_id=next_page_id,
        )

    async def get_conversation_callback(
        self, callback_id: UUID
    ) -> ConversationCallback | None:
        """
        Get a single conversation callback by ID.

        Args:
            callback_id: The callback ID to retrieve

        Returns:
            ConversationCallback | None: The callback if found, None otherwise
        """
        query = select(StoredConversationCallback).where(
            StoredConversationCallback.id == callback_id
        )
        result = await self.session.execute(query)
        stored_callback = result.scalar_one_or_none()

        if stored_callback is None:
            return None

        return stored_callback.to_pydantic()

    async def batch_get_conversation_callbacks(
        self, callback_ids: list[UUID]
    ) -> list[ConversationCallback | None]:
        """
        Get multiple conversation callbacks by their IDs.

        Args:
            callback_ids: List of callback IDs to retrieve

        Returns:
            list[ConversationCallback | None]: List of callbacks, None for missing ones
        """
        if not callback_ids:
            return []

        query = select(StoredConversationCallback).where(
            StoredConversationCallback.id.in_(callback_ids)
        )
        result = await self.session.execute(query)
        stored_callbacks = result.scalars().all()

        # Create a mapping of ID to callback
        callback_map = {
            callback.id: callback.to_pydantic() for callback in stored_callbacks
        }

        # Return results in the same order as requested, with None for missing callbacks
        return [callback_map.get(callback_id) for callback_id in callback_ids]

    async def create_conversation_callback(
        self, callback: ConversationCallback
    ) -> ConversationCallback:
        """
        Create a new conversation callback.

        Args:
            callback: The callback to create

        Returns:
            ConversationCallback: The created callback
        """
        stored_callback = StoredConversationCallback.from_pydantic(callback)
        self.session.add(stored_callback)
        await self.session.commit()
        await self.session.refresh(stored_callback)

        return stored_callback.to_pydantic()

    async def update_conversation_callback(
        self, callback_id: UUID, updates: dict[str, Any]
    ) -> ConversationCallback | None:
        """
        Update a conversation callback.

        Args:
            callback_id: The ID of the callback to update
            updates: Dictionary of fields to update

        Returns:
            ConversationCallback | None: The updated callback if found, None otherwise
        """
        query = select(StoredConversationCallback).where(
            StoredConversationCallback.id == callback_id
        )
        result = await self.session.execute(query)
        stored_callback = result.scalar_one_or_none()

        if stored_callback is None:
            return None

        # Apply updates
        for field, value in updates.items():
            if field == "status" and isinstance(value, ConversationCallbackStatus):
                stored_callback.status = value.value
            elif field == "processor":
                stored_callback.processor = value
            elif hasattr(stored_callback, field):
                setattr(stored_callback, field, value)

        await self.session.commit()
        await self.session.refresh(stored_callback)

        return stored_callback.to_pydantic()

    async def delete_conversation_callback(self, callback_id: UUID) -> bool:
        """
        Delete a conversation callback.

        Args:
            callback_id: The ID of the callback to delete

        Returns:
            bool: True if the callback was deleted, False if not found
        """
        query = select(StoredConversationCallback).where(
            StoredConversationCallback.id == callback_id
        )
        result = await self.session.execute(query)
        stored_callback = result.scalar_one_or_none()

        if stored_callback is None:
            return False

        await self.session.delete(stored_callback)
        await self.session.commit()

        return True

    async def get_callbacks_for_conversation(
        self, conversation_id: UUID, status: ConversationCallbackStatus | None = None
    ) -> list[ConversationCallback]:
        """
        Get all callbacks for a specific conversation.

        Args:
            conversation_id: The conversation ID
            status: Optional status filter

        Returns:
            list[ConversationCallback]: List of callbacks for the conversation
        """
        query = select(StoredConversationCallback).where(
            StoredConversationCallback.conversation_id == conversation_id
        )

        if status is not None:
            query = query.where(StoredConversationCallback.status == status.value)

        query = query.order_by(desc(StoredConversationCallback.created_at))

        result = await self.session.execute(query)
        stored_callbacks = result.scalars().all()

        return [callback.to_pydantic() for callback in stored_callbacks]

    async def get_callbacks_by_event_kind(
        self, event_kind: str, status: ConversationCallbackStatus | None = None
    ) -> list[ConversationCallback]:
        """
        Get all callbacks for a specific event kind.

        Args:
            event_kind: The event kind to filter by
            status: Optional status filter

        Returns:
            list[ConversationCallback]: List of callbacks for the event kind
        """
        query = select(StoredConversationCallback).where(
            StoredConversationCallback.event_kind == event_kind
        )

        if status is not None:
            query = query.where(StoredConversationCallback.status == status.value)

        query = query.order_by(desc(StoredConversationCallback.created_at))

        result = await self.session.execute(query)
        stored_callbacks = result.scalars().all()

        return [callback.to_pydantic() for callback in stored_callbacks]
