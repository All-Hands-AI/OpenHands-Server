"""
Unit tests for SQLAlchemyConversationCallbackContext.

Tests cover all CRUD operations, filtering, pagination, and error handling
for the SQLAlchemy implementation of ConversationCallbackContext.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.conversation_callback.conversation_callback_database_models import (
    StoredConversationCallback,
)
from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackPage,
    ConversationCallbackStatus,
    LoggingCallbackProcessor,
)
from openhands_server.conversation_callback.sqlalchemy_conversation_callback_context import (
    SQLAlchemyConversationCallbackContext,
)


class TestSQLAlchemyConversationCallbackContext:
    """Test cases for SQLAlchemyConversationCallbackContext."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession for testing."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def context(self, mock_session):
        """Create a SQLAlchemyConversationCallbackContext instance for testing."""
        return SQLAlchemyConversationCallbackContext(mock_session)

    @pytest.fixture
    def sample_callback_id(self):
        """Generate a sample callback ID for testing."""
        return uuid4()

    @pytest.fixture
    def sample_conversation_id(self):
        """Generate a sample conversation ID for testing."""
        return uuid4()

    @pytest.fixture
    def sample_callback(self, sample_callback_id, sample_conversation_id):
        """Create a sample ConversationCallback for testing."""
        return ConversationCallback(
            id=sample_callback_id,
            status=ConversationCallbackStatus.ACTIVE,
            conversation_id=sample_conversation_id,
            processor=LoggingCallbackProcessor(),
            event_kind="test_event",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_stored_callback(self, sample_callback):
        """Create a sample StoredConversationCallback for testing."""
        return StoredConversationCallback.from_pydantic(sample_callback)

    @pytest.mark.asyncio
    async def test_get_instance(self):
        """Test getting an instance of the context from a request."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)

        with patch(
            "openhands_server.conversation_callback.sqlalchemy_conversation_callback_context.async_session_dependency"
        ) as mock_dependency:
            # Mock the async generator
            async def mock_generator(request):
                yield mock_session

            mock_dependency.return_value = mock_generator(mock_request)

            context = await SQLAlchemyConversationCallbackContext.get_instance(
                mock_request
            )

            assert isinstance(context, SQLAlchemyConversationCallbackContext)
            assert context.session == mock_session

    @pytest.mark.asyncio
    async def test_search_conversation_callbacks_no_filters(
        self, context, mock_session, sample_stored_callback
    ):
        """Test searching for conversation callbacks without filters."""
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        page = await context.search_conversation_callbacks()

        assert isinstance(page, ConversationCallbackPage)
        assert len(page.items) == 1
        assert page.items[0].id == sample_stored_callback.id
        assert page.next_page_id is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_conversation_callbacks_with_filters(
        self, context, mock_session, sample_stored_callback, sample_conversation_id
    ):
        """Test searching for conversation callbacks with filters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        page = await context.search_conversation_callbacks(
            conversation_id=sample_conversation_id,
            status=ConversationCallbackStatus.ACTIVE,
            event_kind="test_event",
            limit=50,
        )

        assert isinstance(page, ConversationCallbackPage)
        assert len(page.items) == 1
        assert page.items[0].id == sample_stored_callback.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_conversation_callbacks_with_pagination(
        self, context, mock_session, sample_stored_callback
    ):
        """Test searching for conversation callbacks with pagination."""
        # Create multiple callbacks to test pagination
        callbacks = [sample_stored_callback] * 6  # More than limit of 5
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = callbacks
        mock_session.execute.return_value = mock_result

        page = await context.search_conversation_callbacks(limit=5)

        assert isinstance(page, ConversationCallbackPage)
        assert len(page.items) == 5  # Limited to 5
        assert page.next_page_id == str(callbacks[4].id)  # Should have next page
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_conversation_callbacks_with_page_id(
        self, context, mock_session, sample_stored_callback
    ):
        """Test searching for conversation callbacks with page ID."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        page_id = str(uuid4())
        page = await context.search_conversation_callbacks(page_id=page_id)

        assert isinstance(page, ConversationCallbackPage)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_conversation_callbacks_invalid_page_id(
        self, context, mock_session, sample_stored_callback
    ):
        """Test searching for conversation callbacks with invalid page ID."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        # Invalid UUID should be ignored
        page = await context.search_conversation_callbacks(page_id="invalid-uuid")

        assert isinstance(page, ConversationCallbackPage)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_callback_found(
        self, context, mock_session, sample_stored_callback, sample_callback_id
    ):
        """Test getting a conversation callback that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_stored_callback
        mock_session.execute.return_value = mock_result

        callback = await context.get_conversation_callback(sample_callback_id)

        assert callback is not None
        assert callback.id == sample_stored_callback.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_callback_not_found(
        self, context, mock_session, sample_callback_id
    ):
        """Test getting a conversation callback that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        callback = await context.get_conversation_callback(sample_callback_id)

        assert callback is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_get_conversation_callbacks_empty_list(self, context):
        """Test batch getting conversation callbacks with empty list."""
        result = await context.batch_get_conversation_callbacks([])

        assert result == []

    @pytest.mark.asyncio
    async def test_batch_get_conversation_callbacks_found(
        self, context, mock_session, sample_stored_callback
    ):
        """Test batch getting conversation callbacks that exist."""
        callback_ids = [sample_stored_callback.id, uuid4()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        callbacks = await context.batch_get_conversation_callbacks(callback_ids)

        assert len(callbacks) == 2
        assert callbacks[0] is not None
        assert callbacks[0].id == sample_stored_callback.id
        assert callbacks[1] is None  # Second ID not found
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_callback(
        self, context, mock_session, sample_callback, sample_stored_callback
    ):
        """Test creating a new conversation callback."""
        # Mock the session operations
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch(
            "openhands_server.conversation_callback.conversation_callback_database_models.StoredConversationCallback.from_pydantic",
            return_value=sample_stored_callback,
        ):
            created_callback = await context.create_conversation_callback(sample_callback)

            assert created_callback.id == sample_callback.id
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_callback_found(
        self, context, mock_session, sample_stored_callback, sample_callback_id
    ):
        """Test updating a conversation callback that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_stored_callback
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        updates = {
            "status": ConversationCallbackStatus.COMPLETED,
            "event_kind": "updated_event",
        }

        updated_callback = await context.update_conversation_callback(
            sample_callback_id, updates
        )

        assert updated_callback is not None
        assert updated_callback.id == sample_stored_callback.id
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_callback_not_found(
        self, context, mock_session, sample_callback_id
    ):
        """Test updating a conversation callback that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        updates = {"status": ConversationCallbackStatus.COMPLETED}

        updated_callback = await context.update_conversation_callback(
            sample_callback_id, updates
        )

        assert updated_callback is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_callback_with_processor(
        self, context, mock_session, sample_stored_callback, sample_callback_id
    ):
        """Test updating a conversation callback with processor."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_stored_callback
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        new_processor = LoggingCallbackProcessor()
        updates = {"processor": new_processor}

        updated_callback = await context.update_conversation_callback(
            sample_callback_id, updates
        )

        assert updated_callback is not None
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_callback_found(
        self, context, mock_session, sample_stored_callback, sample_callback_id
    ):
        """Test deleting a conversation callback that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_stored_callback
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        result = await context.delete_conversation_callback(sample_callback_id)

        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.delete.assert_called_once_with(sample_stored_callback)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_callback_not_found(
        self, context, mock_session, sample_callback_id
    ):
        """Test deleting a conversation callback that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await context.delete_conversation_callback(sample_callback_id)

        assert result is False
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_callbacks_for_conversation(
        self, context, mock_session, sample_stored_callback, sample_conversation_id
    ):
        """Test getting all callbacks for a specific conversation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        callbacks = await context.get_callbacks_for_conversation(sample_conversation_id)

        assert len(callbacks) == 1
        assert callbacks[0].id == sample_stored_callback.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_callbacks_for_conversation_with_status_filter(
        self, context, mock_session, sample_stored_callback, sample_conversation_id
    ):
        """Test getting callbacks for a conversation with status filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        callbacks = await context.get_callbacks_for_conversation(
            sample_conversation_id, status=ConversationCallbackStatus.ACTIVE
        )

        assert len(callbacks) == 1
        assert callbacks[0].id == sample_stored_callback.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_callbacks_by_event_kind(
        self, context, mock_session, sample_stored_callback
    ):
        """Test getting all callbacks for a specific event kind."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        callbacks = await context.get_callbacks_by_event_kind("test_event")

        assert len(callbacks) == 1
        assert callbacks[0].id == sample_stored_callback.id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_callbacks_by_event_kind_with_status_filter(
        self, context, mock_session, sample_stored_callback
    ):
        """Test getting callbacks by event kind with status filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_stored_callback]
        mock_session.execute.return_value = mock_result

        callbacks = await context.get_callbacks_by_event_kind(
            "test_event", status=ConversationCallbackStatus.ACTIVE
        )

        assert len(callbacks) == 1
        assert callbacks[0].id == sample_stored_callback.id
        mock_session.execute.assert_called_once()


class TestStoredConversationCallbackModel:
    """Test cases for the StoredConversationCallback SQLAlchemy model."""

    @pytest.fixture
    def sample_callback_data(self):
        """Create sample callback data for testing."""
        return {
            "id": uuid4(),
            "status": ConversationCallbackStatus.ACTIVE,
            "conversation_id": uuid4(),
            "processor": LoggingCallbackProcessor(),
            "event_kind": "test_event",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    def test_stored_callback_from_pydantic(self, sample_callback_data):
        """Test creating StoredConversationCallback from Pydantic model."""
        pydantic_callback = ConversationCallback(**sample_callback_data)
        stored_callback = StoredConversationCallback.from_pydantic(pydantic_callback)

        assert stored_callback.id == pydantic_callback.id
        assert stored_callback.status == pydantic_callback.status.value
        assert stored_callback.conversation_id == pydantic_callback.conversation_id
        assert stored_callback.event_kind == pydantic_callback.event_kind
        assert stored_callback.created_at == pydantic_callback.created_at
        assert stored_callback.updated_at == pydantic_callback.updated_at

    def test_stored_callback_to_pydantic(self, sample_callback_data):
        """Test converting StoredConversationCallback to Pydantic model."""
        pydantic_callback = ConversationCallback(**sample_callback_data)
        stored_callback = StoredConversationCallback.from_pydantic(pydantic_callback)
        
        # Convert back to Pydantic
        converted_callback = stored_callback.to_pydantic()

        assert converted_callback.id == pydantic_callback.id
        assert converted_callback.status == pydantic_callback.status
        assert converted_callback.conversation_id == pydantic_callback.conversation_id
        assert converted_callback.event_kind == pydantic_callback.event_kind
        assert converted_callback.created_at == pydantic_callback.created_at
        assert converted_callback.updated_at == pydantic_callback.updated_at

    def test_processor_property_serialization(self, sample_callback_data):
        """Test processor property serialization and deserialization."""
        pydantic_callback = ConversationCallback(**sample_callback_data)
        stored_callback = StoredConversationCallback.from_pydantic(pydantic_callback)

        # Test that processor_data is set correctly
        assert stored_callback.processor_data is not None
        assert isinstance(stored_callback.processor_data, dict)

        # Test that processor property returns the correct type
        processor = stored_callback.processor
        assert isinstance(processor, LoggingCallbackProcessor)

    def test_status_enum_property(self, sample_callback_data):
        """Test status enum property conversion."""
        pydantic_callback = ConversationCallback(**sample_callback_data)
        stored_callback = StoredConversationCallback.from_pydantic(pydantic_callback)

        # Test getting status as enum
        assert stored_callback.status_enum == ConversationCallbackStatus.ACTIVE

        # Test setting status from enum
        stored_callback.status_enum = ConversationCallbackStatus.COMPLETED
        assert stored_callback.status == ConversationCallbackStatus.COMPLETED.value
        assert stored_callback.status_enum == ConversationCallbackStatus.COMPLETED

    def test_processor_property_none_handling(self):
        """Test processor property handling of None values."""
        stored_callback = StoredConversationCallback()
        stored_callback.processor_data = None

        # Should raise ValueError when trying to get processor with None data
        with pytest.raises(ValueError, match="Processor data is None"):
            _ = stored_callback.processor

        # Should set processor_data to None when setting processor to None
        stored_callback.processor = None
        assert stored_callback.processor_data is None

    def test_roundtrip_conversion(self, sample_callback_data):
        """Test complete roundtrip conversion between Pydantic and SQLAlchemy models."""
        # Start with Pydantic model
        original_callback = ConversationCallback(**sample_callback_data)
        
        # Convert to SQLAlchemy model
        stored_callback = StoredConversationCallback.from_pydantic(original_callback)
        
        # Convert back to Pydantic model
        converted_callback = stored_callback.to_pydantic()
        
        # Verify all fields match
        assert converted_callback.id == original_callback.id
        assert converted_callback.status == original_callback.status
        assert converted_callback.conversation_id == original_callback.conversation_id
        assert converted_callback.event_kind == original_callback.event_kind
        assert converted_callback.created_at == original_callback.created_at
        assert converted_callback.updated_at == original_callback.updated_at
        
        # Verify processor is correctly serialized/deserialized
        assert type(converted_callback.processor) == type(original_callback.processor)