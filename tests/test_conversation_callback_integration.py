"""
Integration tests for conversation callback database models.

These tests use an in-memory SQLite database to test the actual database
operations without mocking.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from openhands_server.conversation_callback.conversation_callback_database_models import (
    StoredConversationCallback,
)
from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackStatus,
    LoggingCallbackProcessor,
)
from openhands_server.conversation_callback.sqlalchemy_conversation_callback_context import (
    SQLAlchemyConversationCallbackContext,
)
from openhands_server.database import Base


class TestConversationCallbackIntegration:
    """Integration tests for conversation callback functionality."""

    @pytest.fixture
    async def async_engine(self):
        """Create an async SQLite engine for testing."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield engine
        
        # Clean up
        await engine.dispose()

    @pytest.fixture
    async def async_session(self, async_engine):
        """Create an async session for testing."""
        async_session_maker = async_sessionmaker(
            async_engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session_maker() as session:
            yield session

    @pytest.fixture
    async def context(self, async_session):
        """Create a SQLAlchemyConversationCallbackContext for testing."""
        return SQLAlchemyConversationCallbackContext(async_session)

    @pytest.fixture
    def sample_callback_data(self):
        """Create sample callback data for testing."""
        return {
            "id": uuid.uuid4(),
            "status": ConversationCallbackStatus.ACTIVE,
            "conversation_id": uuid.uuid4(),
            "processor": LoggingCallbackProcessor(),
            "event_kind": "test_event",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.mark.asyncio
    async def test_create_and_retrieve_callback(self, context, sample_callback_data):
        """Test creating and retrieving a conversation callback."""
        # Create a callback
        callback = ConversationCallback(**sample_callback_data)
        created_callback = await context.create_conversation_callback(callback)
        
        assert created_callback.id == callback.id
        assert created_callback.status == callback.status
        assert created_callback.conversation_id == callback.conversation_id
        assert created_callback.event_kind == callback.event_kind
        
        # Retrieve the callback
        retrieved_callback = await context.get_conversation_callback(callback.id)
        
        assert retrieved_callback is not None
        assert retrieved_callback.id == callback.id
        assert retrieved_callback.status == callback.status
        assert retrieved_callback.conversation_id == callback.conversation_id
        assert retrieved_callback.event_kind == callback.event_kind

    @pytest.mark.asyncio
    async def test_update_callback(self, context, sample_callback_data):
        """Test updating a conversation callback."""
        # Create a callback
        callback = ConversationCallback(**sample_callback_data)
        await context.create_conversation_callback(callback)
        
        # Update the callback
        updates = {
            "status": ConversationCallbackStatus.COMPLETED,
            "event_kind": "updated_event",
        }
        updated_callback = await context.update_conversation_callback(
            callback.id, updates
        )
        
        assert updated_callback is not None
        assert updated_callback.status == ConversationCallbackStatus.COMPLETED
        assert updated_callback.event_kind == "updated_event"
        
        # Verify the update persisted
        retrieved_callback = await context.get_conversation_callback(callback.id)
        assert retrieved_callback.status == ConversationCallbackStatus.COMPLETED
        assert retrieved_callback.event_kind == "updated_event"

    @pytest.mark.asyncio
    async def test_delete_callback(self, context, sample_callback_data):
        """Test deleting a conversation callback."""
        # Create a callback
        callback = ConversationCallback(**sample_callback_data)
        await context.create_conversation_callback(callback)
        
        # Verify it exists
        retrieved_callback = await context.get_conversation_callback(callback.id)
        assert retrieved_callback is not None
        
        # Delete the callback
        result = await context.delete_conversation_callback(callback.id)
        assert result is True
        
        # Verify it's gone
        retrieved_callback = await context.get_conversation_callback(callback.id)
        assert retrieved_callback is None

    @pytest.mark.asyncio
    async def test_search_callbacks_with_filters(self, context):
        """Test searching for callbacks with various filters."""
        conversation_id_1 = uuid.uuid4()
        conversation_id_2 = uuid.uuid4()
        
        # Create multiple callbacks
        callbacks_data = [
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.ACTIVE,
                "conversation_id": conversation_id_1,
                "processor": LoggingCallbackProcessor(),
                "event_kind": "event_type_1",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.COMPLETED,
                "conversation_id": conversation_id_1,
                "processor": LoggingCallbackProcessor(),
                "event_kind": "event_type_2",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.ACTIVE,
                "conversation_id": conversation_id_2,
                "processor": LoggingCallbackProcessor(),
                "event_kind": "event_type_1",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ]
        
        # Create all callbacks
        for callback_data in callbacks_data:
            callback = ConversationCallback(**callback_data)
            await context.create_conversation_callback(callback)
        
        # Test filtering by conversation_id
        page = await context.search_conversation_callbacks(
            conversation_id=conversation_id_1
        )
        assert len(page.items) == 2
        
        # Test filtering by status
        page = await context.search_conversation_callbacks(
            status=ConversationCallbackStatus.ACTIVE
        )
        assert len(page.items) == 2
        
        # Test filtering by event_kind
        page = await context.search_conversation_callbacks(event_kind="event_type_1")
        assert len(page.items) == 2
        
        # Test combined filters
        page = await context.search_conversation_callbacks(
            conversation_id=conversation_id_1,
            status=ConversationCallbackStatus.ACTIVE,
        )
        assert len(page.items) == 1

    @pytest.mark.asyncio
    async def test_batch_get_callbacks(self, context, sample_callback_data):
        """Test batch getting multiple callbacks."""
        # Create multiple callbacks
        callback_1 = ConversationCallback(**sample_callback_data)
        callback_2_data = sample_callback_data.copy()
        callback_2_data["id"] = uuid.uuid4()
        callback_2 = ConversationCallback(**callback_2_data)
        
        await context.create_conversation_callback(callback_1)
        await context.create_conversation_callback(callback_2)
        
        # Test batch get with existing and non-existing IDs
        non_existing_id = uuid.uuid4()
        callback_ids = [callback_1.id, callback_2.id, non_existing_id]
        
        callbacks = await context.batch_get_conversation_callbacks(callback_ids)
        
        assert len(callbacks) == 3
        assert callbacks[0] is not None
        assert callbacks[0].id == callback_1.id
        assert callbacks[1] is not None
        assert callbacks[1].id == callback_2.id
        assert callbacks[2] is None  # Non-existing callback

    @pytest.mark.asyncio
    async def test_get_callbacks_for_conversation(self, context):
        """Test getting all callbacks for a specific conversation."""
        conversation_id = uuid.uuid4()
        other_conversation_id = uuid.uuid4()
        
        # Create callbacks for different conversations
        callback_1_data = {
            "id": uuid.uuid4(),
            "status": ConversationCallbackStatus.ACTIVE,
            "conversation_id": conversation_id,
            "processor": LoggingCallbackProcessor(),
            "event_kind": "event_1",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        callback_2_data = {
            "id": uuid.uuid4(),
            "status": ConversationCallbackStatus.COMPLETED,
            "conversation_id": conversation_id,
            "processor": LoggingCallbackProcessor(),
            "event_kind": "event_2",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        callback_3_data = {
            "id": uuid.uuid4(),
            "status": ConversationCallbackStatus.ACTIVE,
            "conversation_id": other_conversation_id,
            "processor": LoggingCallbackProcessor(),
            "event_kind": "event_1",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        # Create all callbacks
        await context.create_conversation_callback(ConversationCallback(**callback_1_data))
        await context.create_conversation_callback(ConversationCallback(**callback_2_data))
        await context.create_conversation_callback(ConversationCallback(**callback_3_data))
        
        # Get callbacks for specific conversation
        callbacks = await context.get_callbacks_for_conversation(conversation_id)
        assert len(callbacks) == 2
        
        # Get callbacks for specific conversation with status filter
        active_callbacks = await context.get_callbacks_for_conversation(
            conversation_id, status=ConversationCallbackStatus.ACTIVE
        )
        assert len(active_callbacks) == 1
        assert active_callbacks[0].status == ConversationCallbackStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_callbacks_by_event_kind(self, context):
        """Test getting all callbacks for a specific event kind."""
        # Create callbacks with different event kinds
        callbacks_data = [
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.ACTIVE,
                "conversation_id": uuid.uuid4(),
                "processor": LoggingCallbackProcessor(),
                "event_kind": "common_event",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.COMPLETED,
                "conversation_id": uuid.uuid4(),
                "processor": LoggingCallbackProcessor(),
                "event_kind": "common_event",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "status": ConversationCallbackStatus.ACTIVE,
                "conversation_id": uuid.uuid4(),
                "processor": LoggingCallbackProcessor(),
                "event_kind": "different_event",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ]
        
        # Create all callbacks
        for callback_data in callbacks_data:
            callback = ConversationCallback(**callback_data)
            await context.create_conversation_callback(callback)
        
        # Get callbacks by event kind
        callbacks = await context.get_callbacks_by_event_kind("common_event")
        assert len(callbacks) == 2
        
        # Get callbacks by event kind with status filter
        active_callbacks = await context.get_callbacks_by_event_kind(
            "common_event", status=ConversationCallbackStatus.ACTIVE
        )
        assert len(active_callbacks) == 1
        assert active_callbacks[0].status == ConversationCallbackStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_processor_serialization_roundtrip(self, context, sample_callback_data):
        """Test that processor serialization works correctly in database operations."""
        # Create a callback with a processor
        callback = ConversationCallback(**sample_callback_data)
        created_callback = await context.create_conversation_callback(callback)
        
        # Verify the processor is correctly serialized and deserialized
        assert isinstance(created_callback.processor, LoggingCallbackProcessor)
        
        # Retrieve the callback and verify processor is still correct
        retrieved_callback = await context.get_conversation_callback(callback.id)
        assert retrieved_callback is not None
        assert isinstance(retrieved_callback.processor, LoggingCallbackProcessor)
        
        # Update the callback with a new processor
        new_processor = LoggingCallbackProcessor()
        updates = {"processor": new_processor}
        updated_callback = await context.update_conversation_callback(
            callback.id, updates
        )
        
        assert updated_callback is not None
        assert isinstance(updated_callback.processor, LoggingCallbackProcessor)