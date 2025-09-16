"""
Subscriber models for the OpenHands SDK Server.

This module defines the SerializableSubscriber base model and concrete implementations
like WebHookSubscriber for handling event subscriptions in conversations.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from openhands.sdk import EventBase


logger = logging.getLogger(__name__)


class SubscriberInterface(ABC):
    """Interface for subscribers that can be used with PubSub.
    
    Provides async context manager methods for proper resource management.
    """
    
    @abstractmethod
    async def __aenter__(self):
        """Enter the async context manager."""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        pass
    
    @abstractmethod
    async def __call__(self, event: EventBase):
        """Handle an incoming event."""
        pass


class SerializableSubscriber(BaseModel, SubscriberInterface):
    """
    Base model for serializable subscribers using discriminated union.
    
    This allows for proper serialization/deserialization of different subscriber types
    while maintaining type safety and validation.
    """
    
    id: UUID = Field(default_factory=uuid4)
    type: str = Field(..., description="Discriminator field for subscriber type")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        # Enable discriminated union based on 'type' field
        discriminator = 'type'
        arbitrary_types_allowed = True
        
    async def __aenter__(self):
        """Default implementation - subclasses can override."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Default implementation - subclasses can override."""
        pass


class WebHookSubscriber(SerializableSubscriber):
    """
    WebHook subscriber that batches events and posts them to a URL.
    
    Features:
    - Batches events until max_batch_size is reached or max_wait_time elapses
    - Filters events by type if filter_types is specified
    - Uses session API key as authorization header if present
    - Automatically flushes pending events when unsubscribed
    """
    
    type: Literal["webhook"] = "webhook"
    url: str = Field(..., description="URL to POST batched events to")
    max_batch_size: int = Field(default=10, ge=1, description="Maximum events per batch")
    max_wait_time: int = Field(default=30, ge=1, description="Maximum seconds to wait before sending batch")
    filter_types: Optional[list[str]] = Field(default=None, description="Event types to include (None = all)")
    session_api_key: Optional[str] = Field(default=None, description="API key for authorization header")
    
    # Internal state (not serialized)
    pending_events: list[EventBase] = Field(default_factory=list, exclude=True)
    last_flush_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)
    flush_task: Optional[asyncio.Task] = Field(default=None, exclude=True)
    http_client: Optional[httpx.AsyncClient] = Field(default=None, exclude=True)
    
    async def __aenter__(self):
        """Initialize the HTTP client and start the flush timer."""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.last_flush_time = datetime.now(timezone.utc)
        self._schedule_flush()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources and flush any pending events."""
        # Cancel the flush task
        if self.flush_task and not self.flush_task.done():
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush any remaining events
        await self._flush_events()
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
    
    async def __call__(self, event: EventBase):
        """Handle an incoming event by adding it to the batch."""
        # Filter events if filter_types is specified
        if self.filter_types is not None:
            if event.type not in self.filter_types:
                return
        
        self.pending_events.append(event)
        logger.debug(f"Added event {event.id} to webhook batch. Pending: {len(self.pending_events)}")
        
        # Check if we should flush immediately
        if len(self.pending_events) >= self.max_batch_size:
            await self._flush_events()
    
    def _schedule_flush(self):
        """Schedule the next flush based on max_wait_time."""
        if self.flush_task and not self.flush_task.done():
            self.flush_task.cancel()
        
        self.flush_task = asyncio.create_task(self._wait_and_flush())
    
    async def _wait_and_flush(self):
        """Wait for max_wait_time and then flush events."""
        try:
            await asyncio.sleep(self.max_wait_time)
            await self._flush_events()
        except asyncio.CancelledError:
            # Task was cancelled, which is fine
            pass
    
    async def _flush_events(self):
        """Flush pending events to the webhook URL."""
        if not self.pending_events:
            return
        
        if not self.http_client:
            logger.error("HTTP client not initialized for webhook subscriber")
            return
        
        # Prepare the batch
        events_to_send = self.pending_events.copy()
        self.pending_events.clear()
        self.last_flush_time = datetime.now(timezone.utc)
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if self.session_api_key:
            headers["Authorization"] = f"Bearer {self.session_api_key}"
        
        # Prepare payload
        payload = {
            "subscriber_id": str(self.id),
            "timestamp": self.last_flush_time.isoformat(),
            "events": [event.model_dump() for event in events_to_send]
        }
        
        try:
            response = await self.http_client.post(
                self.url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Successfully sent {len(events_to_send)} events to webhook {self.url}")
        except Exception as e:
            logger.error(f"Failed to send events to webhook {self.url}: {e}")
            # Re-add events to the beginning of the pending list for retry
            self.pending_events = events_to_send + self.pending_events
        
        # Schedule next flush if there are still pending events
        if self.pending_events:
            self._schedule_flush()
    
    async def flush(self):
        """Manually flush all pending events."""
        await self._flush_events()


# Union type for all subscriber types
SubscriberUnion = WebHookSubscriber  # Add more types here as they're implemented