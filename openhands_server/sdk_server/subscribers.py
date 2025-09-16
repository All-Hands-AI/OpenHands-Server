"""
Subscriber models for event notifications.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Discriminator, Field, Tag

from openhands.sdk import EventBase


logger = logging.getLogger(__name__)


class SerializableSubscriber(BaseModel, ABC):
    """Base class for all serializable subscribers."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Human-readable name for the subscriber")
    
    @abstractmethod
    async def notify(self, event: EventBase, session_api_key: str | None = None) -> None:
        """Send notification about an event."""
        pass


class WebSocketSubscriber(SerializableSubscriber):
    """Subscriber that posts events to a URL using HTTP requests."""
    
    type: Literal["websocket"] = "websocket"
    url: str = Field(..., description="URL to post events to")
    filter_types: list[str] | None = Field(
        default=None, 
        description="Optional list of event types to filter. If None, all events are sent."
    )
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")
    
    async def notify(self, event: EventBase, session_api_key: str | None = None) -> None:
        """Post event to the configured URL."""
        # Check if event type should be filtered
        if self.filter_types is not None:
            event_type = event.__class__.__name__
            if event_type not in self.filter_types:
                logger.debug(f"Filtering out event type {event_type} for subscriber {self.name}")
                return
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if session_api_key:
            headers["Authorization"] = f"Bearer {session_api_key}"
        
        # Prepare payload
        payload = event.model_dump()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                logger.debug(f"Successfully posted event to {self.url} for subscriber {self.name}")
        except httpx.TimeoutException:
            logger.error(f"Timeout posting event to {self.url} for subscriber {self.name}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} posting event to {self.url} for subscriber {self.name}")
        except Exception as e:
            logger.error(f"Error posting event to {self.url} for subscriber {self.name}: {e}")


# Discriminated union for all subscriber types
# For now we only have one subscriber type, but this will be a Union when we add more
SubscriberUnion = WebSocketSubscriber


class CreateSubscriberRequest(BaseModel):
    """Request to create a new subscriber."""
    
    subscriber: SubscriberUnion


class UpdateSubscriberRequest(BaseModel):
    """Request to update an existing subscriber."""
    
    subscriber: SubscriberUnion


class SubscriberResponse(BaseModel):
    """Response containing subscriber information."""
    
    subscriber: SubscriberUnion


class SubscriberListResponse(BaseModel):
    """Response containing a list of subscribers."""
    
    subscribers: list[SubscriberUnion]


class SubscriberManager:
    """Manages subscribers for a conversation."""
    
    def __init__(self):
        self._subscribers: dict[UUID, SubscriberUnion] = {}
    
    def add_subscriber(self, subscriber: SubscriberUnion) -> UUID:
        """Add a subscriber and return its ID."""
        self._subscribers[subscriber.id] = subscriber
        logger.info(f"Added subscriber {subscriber.name} with ID {subscriber.id}")
        return subscriber.id
    
    def remove_subscriber(self, subscriber_id: UUID) -> bool:
        """Remove a subscriber by ID. Returns True if found and removed."""
        if subscriber_id in self._subscribers:
            subscriber = self._subscribers.pop(subscriber_id)
            logger.info(f"Removed subscriber {subscriber.name} with ID {subscriber_id}")
            return True
        return False
    
    def get_subscriber(self, subscriber_id: UUID) -> SubscriberUnion | None:
        """Get a subscriber by ID."""
        return self._subscribers.get(subscriber_id)
    
    def list_subscribers(self) -> list[SubscriberUnion]:
        """List all subscribers."""
        return list(self._subscribers.values())
    
    async def notify_all(self, event: EventBase, session_api_key: str | None = None) -> None:
        """Notify all subscribers about an event."""
        if not self._subscribers:
            return
        
        # Create tasks for all notifications to run concurrently
        tasks = []
        for subscriber in self._subscribers.values():
            task = asyncio.create_task(
                subscriber.notify(event, session_api_key),
                name=f"notify_{subscriber.name}_{subscriber.id}"
            )
            tasks.append(task)
        
        # Wait for all notifications to complete (don't fail if some fail)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)