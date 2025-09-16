"""
Subscriber router for OpenHands SDK.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from openhands_server.sdk_server.conversation_service import (
    get_default_conversation_service,
)
from openhands_server.sdk_server.models import Success
from openhands_server.sdk_server.subscribers import (
    CreateSubscriberRequest,
    SubscriberListResponse,
    SubscriberResponse,
    UpdateSubscriberRequest,
)


router = APIRouter(prefix="/conversations/{conversation_id}/subscribers")
conversation_service = get_default_conversation_service()
logger = logging.getLogger(__name__)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subscriber(
    conversation_id: UUID, request: CreateSubscriberRequest
) -> SubscriberResponse:
    """Create a new subscriber for a conversation."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    subscriber_id = await event_service.add_subscriber(request.subscriber)
    # Update the subscriber ID in case it was generated
    request.subscriber.id = subscriber_id
    
    return SubscriberResponse(subscriber=request.subscriber)


@router.get("/")
async def list_subscribers(conversation_id: UUID) -> SubscriberListResponse:
    """List all subscribers for a conversation."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    subscribers = await event_service.list_subscribers()
    return SubscriberListResponse(subscribers=subscribers)


@router.get("/{subscriber_id}")
async def get_subscriber(
    conversation_id: UUID, subscriber_id: UUID
) -> SubscriberResponse:
    """Get a specific subscriber by ID."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    subscriber = await event_service.get_subscriber(subscriber_id)
    if subscriber is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscriber not found")
    
    return SubscriberResponse(subscriber=subscriber)


@router.put("/{subscriber_id}")
async def update_subscriber(
    conversation_id: UUID, subscriber_id: UUID, request: UpdateSubscriberRequest
) -> SubscriberResponse:
    """Update an existing subscriber."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    # Check if subscriber exists
    existing_subscriber = await event_service.get_subscriber(subscriber_id)
    if existing_subscriber is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscriber not found")
    
    # Update the subscriber ID to match the path parameter
    request.subscriber.id = subscriber_id
    
    # Remove the old subscriber and add the updated one
    await event_service.remove_subscriber(subscriber_id)
    await event_service.add_subscriber(request.subscriber)
    
    return SubscriberResponse(subscriber=request.subscriber)


@router.delete("/{subscriber_id}")
async def delete_subscriber(conversation_id: UUID, subscriber_id: UUID) -> Success:
    """Delete a subscriber by ID."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    removed = await event_service.remove_subscriber(subscriber_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscriber not found")
    
    return Success()