"""SQLAlchemy implementation of EventCallbackResultContext."""

from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands.sdk.event.types import EventID
from openhands_server.database import async_session_dependency
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContext,
    EventCallbackResultContextFactory,
)
from openhands_server.event_callback.event_callback_result_db_models import (
    StoredEventCallbackResult,
)
from openhands_server.event_callback.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultPage,
    EventCallbackResultSortOrder,
)


class SQLAlchemyEventCallbackResultContext(EventCallbackResultContext):
    """SQLAlchemy implementation of EventCallbackResultContext."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the context with a database session.

        Args:
            session: The SQLAlchemy async session
        """
        self.session = session

    async def get_event_callback_result(self, id: UUID) -> EventCallbackResult | None:
        """
        Get a single event callback result, returning None if not found.

        Args:
            id: The event callback result ID to retrieve

        Returns:
            EventCallbackResult | None: The result if found, None otherwise
        """
        query = select(StoredEventCallbackResult).where(
            StoredEventCallbackResult.id == id
        )
        result = await self.session.execute(query)
        stored_result = result.scalar_one_or_none()

        if stored_result is None:
            return None

        return stored_result.to_pydantic()

    async def search_event_callback_results(
        self,
        event_callback_id__eq: UUID | None = None,
        event_id__eq: EventID | None = None,
        conversation_id__eq: UUID | None = None,
        sort_order: EventCallbackResultSortOrder = (
            EventCallbackResultSortOrder.created_at
        ),
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventCallbackResultPage:
        """
        Search for event callback results, optionally filtered by
        callback_id, event_id or conversation_id, and sorting by created_at
        ascending or descending.

        Args:
            event_callback_id__eq: Optional event callback ID filter
            event_id__eq: Optional event ID filter
            conversation_id__eq: Optional conversation ID filter
            sort_order: Sort order for results
            page_id: Optional page ID for pagination (UUID string)
            limit: Maximum number of results to return

        Returns:
            EventCallbackResultPage: Page of event callback results
        """
        query = select(StoredEventCallbackResult)

        # Apply filters
        conditions = []
        if event_callback_id__eq is not None:
            conditions.append(
                StoredEventCallbackResult.event_callback_id == event_callback_id__eq
            )
        if event_id__eq is not None:
            conditions.append(StoredEventCallbackResult.event_id == event_id__eq)
        if conversation_id__eq is not None:
            conditions.append(
                StoredEventCallbackResult.conversation_id == conversation_id__eq
            )

        if conditions:
            query = query.where(and_(*conditions))

        # Apply pagination
        if page_id:
            try:
                page_uuid = UUID(page_id)
                if sort_order == EventCallbackResultSortOrder.created_at_DESC:
                    query = query.where(StoredEventCallbackResult.id < page_uuid)
                else:
                    query = query.where(StoredEventCallbackResult.id > page_uuid)
            except ValueError:
                # Invalid UUID, ignore pagination
                pass

        # Apply sorting
        if sort_order == EventCallbackResultSortOrder.created_at_DESC:
            query = query.order_by(desc(StoredEventCallbackResult.created_at)).order_by(
                desc(StoredEventCallbackResult.id)
            )
        else:
            query = query.order_by(StoredEventCallbackResult.created_at).order_by(
                StoredEventCallbackResult.id
            )

        query = query.limit(limit + 1)

        result = await self.session.execute(query)
        stored_results = result.scalars().all()

        # Convert to Pydantic models
        results = [result.to_pydantic() for result in stored_results[:limit]]

        # Determine next page ID
        next_page_id = None
        if len(stored_results) > limit:
            next_page_id = str(stored_results[limit - 1].id)

        return EventCallbackResultPage(
            items=results,
            next_page_id=next_page_id,
        )

    async def delete_event_callback_result(self, id: UUID) -> bool:
        """
        Delete an event callback result, returning True if deleted,
        False if not found.

        Args:
            id: The ID of the event callback result to delete

        Returns:
            bool: True if the result was deleted, False if not found
        """
        query = select(StoredEventCallbackResult).where(
            StoredEventCallbackResult.id == id
        )
        result = await self.session.execute(query)
        stored_result = result.scalar_one_or_none()

        if stored_result is None:
            return False

        await self.session.delete(stored_result)
        await self.session.commit()

        return True


class SQLAlchemyEventCallbackResultContextFactory(EventCallbackResultContextFactory):
    async def with_instance(
        self,
        session: AsyncSession = Depends(async_session_dependency),
    ) -> AsyncGenerator[EventCallbackResultContext, None]:
        """
        Get an instance of SQLAlchemy event callback result context.

        Args:
            session: The async SQLAlchemy session from dependency injection

        Yields:
            EventCallbackResultContext: The context instance
        """
        context = SQLAlchemyEventCallbackResultContext(session)
        try:
            yield context
        finally:
            # Session cleanup is handled by the dependency
            pass
