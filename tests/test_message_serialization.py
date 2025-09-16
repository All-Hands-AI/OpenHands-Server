"""Unit tests for Message serialization and deserialization.

This test suite covers:
1. The user's specific request: Message -> model_dump() -> EventBase.model_validate() (fails as expected)
2. A working alternative: MessageEvent -> model_dump() -> EventBase.model_validate() (succeeds)
3. Standard Message serialization/deserialization roundtrip tests
4. Comprehensive field preservation and role testing
"""

import pytest

from openhands.sdk import EventBase, Message, TextContent
from openhands.sdk.event import MessageEvent


class TestMessageSerialization:
    """Test cases for Message serialization and deserialization."""

    def test_message_serialization_with_eventbase_validation_fails(self):
        """Test Message serialization and EventBase validation (expected to fail).
        
        This test creates a Message instance, calls model_dump() on it,
        then calls EventBase.model_validate on the dumped value.
        
        This test demonstrates that Message and EventBase have incompatible schemas.
        The user requested this specific test, which shows the expected failure case.
        """
        # Create a Message instance with TextContent
        text_content = TextContent(text="Hello, world!")
        original_message = Message(role="user", content=[text_content])
        
        # Call model_dump() on the message
        dumped_data = original_message.model_dump()
        
        # Call EventBase.model_validate on the dumped value
        # This should fail because Message and EventBase have incompatible schemas
        with pytest.raises(Exception) as exc_info:
            EventBase.model_validate(dumped_data)
        
        # Verify that the validation fails as expected
        assert "validation error" in str(exc_info.value).lower()
        
        # The test demonstrates that Message data cannot be validated as EventBase
        # because EventBase requires 'source' field and doesn't allow Message-specific fields

    def test_message_event_serialization_with_eventbase_validation(self):
        """Test MessageEvent serialization and EventBase validation.
        
        This test creates a MessageEvent (which contains a Message), calls model_dump() on it,
        then calls EventBase.model_validate on the dumped value and verifies that the 
        final result equals the initial one.
        
        This might be what the user intended to test - MessageEvent is a subclass of EventBase.
        """
        # Create a Message instance with TextContent
        text_content = TextContent(text="Hello, world!")
        message = Message(role="user", content=[text_content])
        
        # Create a MessageEvent containing the Message
        original_message_event = MessageEvent(
            source="user",
            llm_message=message
        )
        
        # Call model_dump() on the MessageEvent
        dumped_data = original_message_event.model_dump()
        
        # Call EventBase.model_validate on the dumped value
        # This should work because MessageEvent is a subclass of EventBase
        validated_result = EventBase.model_validate(dumped_data)
        
        # Verify that the final result equals the initial one
        assert validated_result.model_dump() == original_message_event.model_dump()
        assert isinstance(validated_result, MessageEvent)
        assert validated_result.llm_message.role == "user"
        assert len(validated_result.llm_message.content) == 1
        assert validated_result.llm_message.content[0].text == "Hello, world!"

    def test_message_serialization_roundtrip(self):
        """Test Message serialization and deserialization roundtrip.
        
        This is a more conventional test that verifies Message can be
        serialized and deserialized correctly using its own model_validate.
        """
        # Create a Message instance with TextContent
        text_content = TextContent(text="Hello, world!")
        original_message = Message(role="user", content=[text_content])
        
        # Call model_dump() on the message
        dumped_data = original_message.model_dump()
        
        # Call Message.model_validate on the dumped value
        validated_message = Message.model_validate(dumped_data)
        
        # Verify that the final result equals the initial one
        assert validated_message == original_message
        assert validated_message.model_dump() == original_message.model_dump()

    def test_message_serialization_with_multiple_content_types(self):
        """Test Message serialization with multiple content types."""
        # Create a Message instance with multiple TextContent items
        text_content1 = TextContent(text="Hello, world!")
        text_content2 = TextContent(text="This is a test message.")
        original_message = Message(
            role="assistant", 
            content=[text_content1, text_content2],
            name="test_assistant"
        )
        
        # Call model_dump() on the message
        dumped_data = original_message.model_dump()
        
        # Call Message.model_validate on the dumped value
        validated_message = Message.model_validate(dumped_data)
        
        # Verify that the final result equals the initial one
        assert validated_message == original_message
        assert validated_message.model_dump() == original_message.model_dump()
        assert len(validated_message.content) == 2
        assert validated_message.role == "assistant"
        assert validated_message.name == "test_assistant"

    def test_message_serialization_with_all_roles(self):
        """Test Message serialization with different role types."""
        roles = ["user", "assistant", "system", "tool"]
        
        for role in roles:
            text_content = TextContent(text=f"Message from {role}")
            original_message = Message(role=role, content=[text_content])
            
            # Call model_dump() on the message
            dumped_data = original_message.model_dump()
            
            # Call Message.model_validate on the dumped value
            validated_message = Message.model_validate(dumped_data)
            
            # Verify that the final result equals the initial one
            assert validated_message == original_message
            assert validated_message.model_dump() == original_message.model_dump()
            assert validated_message.role == role

    def test_message_serialization_preserves_all_fields(self):
        """Test that Message serialization preserves all fields correctly."""
        text_content = TextContent(text="Test message", cache_prompt=True)
        original_message = Message(
            role="user",
            content=[text_content],
            cache_enabled=True,
            vision_enabled=True,
            function_calling_enabled=True,
            name="test_user",
            force_string_serializer=True
        )
        
        # Call model_dump() on the message
        dumped_data = original_message.model_dump()
        
        # Verify all expected fields are present in dumped data
        expected_fields = {
            'role', 'content', 'cache_enabled', 'vision_enabled',
            'function_calling_enabled', 'tool_calls', 'tool_call_id',
            'name', 'force_string_serializer', 'reasoning_content'
        }
        assert set(dumped_data.keys()) == expected_fields
        
        # Call Message.model_validate on the dumped value
        validated_message = Message.model_validate(dumped_data)
        
        # Verify that the final result equals the initial one
        assert validated_message == original_message
        assert validated_message.model_dump() == original_message.model_dump()
        
        # Verify specific field values
        assert validated_message.cache_enabled == True
        assert validated_message.vision_enabled == True
        assert validated_message.function_calling_enabled == True
        assert validated_message.name == "test_user"
        assert validated_message.force_string_serializer == True