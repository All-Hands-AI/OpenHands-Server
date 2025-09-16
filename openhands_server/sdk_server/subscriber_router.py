"""
Subscriber router for OpenHands SDK Server.

This module provides REST endpoints for managing subscribers to conversation events,
including CRUD operations and subscription management.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from openhands_server.sdk_server.conversation_service import (
    get_default_conversation_service,
)
from openhands_server.sdk_server.models import Success, SubscriberPage
from openhands_server.sdk_server.subscribers import SerializableSubscriber, SubscriberUnion


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations/{conversation_id}/subscribers")
conversation_service = get_default_conversation_service()


class SubscribeRequest(BaseModel):
    """Request to create a new subscriber."""
    subscriber: SubscriberUnion


class SubscribeResponse(BaseModel):
    """Response when creating a new subscriber."""
    subscriber_id: UUID
    success: bool = True


# Read methods

@router.get("/search", responses={404: {"description": "Conversation not found"}})
async def search_conversation_subscribers(
    conversation_id: UUID,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
) -> SubscriberPage:
    """Search / List subscribers for a conversation"""
    assert limit > 0
    assert limit <= 100
    
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    # Get subscribers from the subscriber service
    subscriber_service = await conversation_service.get_subscriber_service(conversation_id)
    if subscriber_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    return await subscriber_service.search_subscribers(page_id, limit)


@router.get("/{subscriber_id}", responses={404: {"description": "Item not found"}})
async def get_conversation_subscriber(
    conversation_id: UUID, subscriber_id: UUID
) -> SerializableSubscriber:
    """Get a subscriber by ID"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscriber_service = await conversation_service.get_subscriber_service(conversation_id)
    if subscriber_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscriber = await subscriber_service.get_subscriber(subscriber_id)
    if subscriber is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    return subscriber


@router.get("/")
async def batch_get_conversation_subscribers(
    conversation_id: UUID, subscriber_ids: list[UUID]
) -> list[SerializableSubscriber | None]:
    """Get a batch of subscribers given their IDs, returning null for any missing item."""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscriber_service = await conversation_service.get_subscriber_service(conversation_id)
    if subscriber_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscribers = await subscriber_service.batch_get_subscribers(subscriber_ids)
    return subscribers


# Write methods

@router.post("/subscribe")
async def subscribe_to_conversation(
    conversation_id: UUID, request: SubscribeRequest
) -> SubscribeResponse:
    """Subscribe to conversation events with a new subscriber"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscriber_service = await conversation_service.get_subscriber_service(conversation_id)
    if subscriber_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    # Validate that the subscriber is a SerializableSubscriber instance
    if not isinstance(request.subscriber, SerializableSubscriber):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Subscriber must be an instance of SerializableSubscriber"
        )
    
    # Subscribe to events
    subscriber_id = await subscriber_service.subscribe(request.subscriber)
    
    return SubscribeResponse(subscriber_id=subscriber_id)


@router.post("/{subscriber_id}/unsubscribe")
async def unsubscribe_from_conversation(
    conversation_id: UUID, subscriber_id: UUID
) -> Success:
    """Unsubscribe from conversation events"""
    event_service = await conversation_service.get_event_service(conversation_id)
    if event_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    subscriber_service = await conversation_service.get_subscriber_service(conversation_id)
    if subscriber_service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    success = await subscriber_service.unsubscribe(subscriber_id)
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    
    return Success()


@router.delete("/{subscriber_id}")
async def delete_conversation_subscriber(
    conversation_id: UUID, subscriber_id: UUID
) -> Success:
    """Delete a subscriber (alias for unsubscribe)"""
    return await unsubscribe_from_conversation(conversation_id, subscriber_id)