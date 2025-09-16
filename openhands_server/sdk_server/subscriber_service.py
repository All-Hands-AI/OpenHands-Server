"""
Subscriber service for managing conversation subscribers.

This service handles the lifecycle of subscribers, including storage, retrieval,
and integration with the PubSub system for event delivery.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from uuid import UUID

from openhands.sdk import EventBase
from openhands_server.sdk_server.models import SubscriberPage
from openhands_server.sdk_server.pub_sub import PubSub
from openhands_server.sdk_server.subscribers import SerializableSubscriber


logger = logging.getLogger(__name__)


@dataclass
class SubscriberService:
    """
    Service for managing subscribers to conversation events.
    
    This service maintains a registry of subscribers, handles their lifecycle,
    and integrates with the PubSub system to deliver events.
    """
    
    conversation_id: UUID
    file_store_path: Path
    pub_sub: PubSub
    
    # Internal state
    _subscribers: Dict[UUID, SerializableSubscriber] = field(default_factory=dict)
    _pubsub_subscriptions: Dict[UUID, UUID] = field(default_factory=dict)
    
    async def get_subscriber(self, subscriber_id: UUID) -> Optional[SerializableSubscriber]:
        """Get a subscriber by ID."""
        return self._subscribers.get(subscriber_id)
    
    async def search_subscribers(
        self, page_id: str | None = None, limit: int = 100
    ) -> SubscriberPage:
        """Search/list subscribers with pagination."""
        items = list(self._subscribers.values())
        
        # Simple pagination - in a real implementation, you might want more sophisticated pagination
        start_index = 0
        if page_id:
            # Find the starting position based on page_id
            for i, subscriber in enumerate(items):
                if str(subscriber.id) == page_id:
                    start_index = i + 1
                    break
        
        # Get the page of items
        page_items = items[start_index:start_index + limit]
        
        # Determine next page ID
        next_page_id = None
        if start_index + limit < len(items):
            next_page_id = str(items[start_index + limit].id)
        
        return SubscriberPage(items=page_items, next_page_id=next_page_id)
    
    async def batch_get_subscribers(
        self, subscriber_ids: list[UUID]
    ) -> list[SerializableSubscriber | None]:
        """Get a batch of subscribers by their IDs."""
        results = []
        for subscriber_id in subscriber_ids:
            subscriber = await self.get_subscriber(subscriber_id)
            results.append(subscriber)
        return results
    
    async def subscribe(self, subscriber: SerializableSubscriber) -> UUID:
        """
        Subscribe a new subscriber to conversation events.
        
        This method:
        1. Stores the subscriber in the registry
        2. Initializes the subscriber (calls __aenter__)
        3. Registers it with the PubSub system
        
        Returns the subscriber ID.
        """
        subscriber_id = subscriber.id
        
        # Store the subscriber
        self._subscribers[subscriber_id] = subscriber
        
        # Initialize the subscriber
        await subscriber.__aenter__()
        
        # Register with PubSub
        pubsub_id = self.pub_sub.subscribe(subscriber)
        self._pubsub_subscriptions[subscriber_id] = pubsub_id
        
        logger.info(f"Subscribed {subscriber.type} subscriber {subscriber_id} to conversation {self.conversation_id}")
        
        # Save state
        await self._save_subscribers()
        
        return subscriber_id
    
    async def unsubscribe(self, subscriber_id: UUID) -> bool:
        """
        Unsubscribe a subscriber from conversation events.
        
        This method:
        1. Removes the subscriber from PubSub
        2. Cleans up the subscriber (calls __aexit__)
        3. Removes it from the registry
        
        Returns True if the subscriber was found and removed, False otherwise.
        """
        subscriber = self._subscribers.get(subscriber_id)
        if subscriber is None:
            return False
        
        # Remove from PubSub
        pubsub_id = self._pubsub_subscriptions.get(subscriber_id)
        if pubsub_id:
            self.pub_sub.unsubscribe(pubsub_id)
            del self._pubsub_subscriptions[subscriber_id]
        
        # Clean up the subscriber
        try:
            await subscriber.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error cleaning up subscriber {subscriber_id}: {e}")
        
        # Remove from registry
        del self._subscribers[subscriber_id]
        
        logger.info(f"Unsubscribed subscriber {subscriber_id} from conversation {self.conversation_id}")
        
        # Save state
        await self._save_subscribers()
        
        return True
    
    async def _save_subscribers(self):
        """Save subscriber state to disk."""
        # For now, we'll keep subscribers in memory only
        # In a production system, you might want to persist them
        pass
    
    async def _load_subscribers(self):
        """Load subscriber state from disk."""
        # For now, we'll keep subscribers in memory only
        # In a production system, you might want to restore them
        pass
    
    async def start(self):
        """Initialize the subscriber service."""
        await self._load_subscribers()
    
    async def close(self):
        """Clean up the subscriber service."""
        # Unsubscribe all subscribers
        subscriber_ids = list(self._subscribers.keys())
        for subscriber_id in subscriber_ids:
            await self.unsubscribe(subscriber_id)
    
    async def __aenter__(self):
        """Enter the async context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        await self.close()
    
    @property
    def subscriber_count(self) -> int:
        """Return the number of active subscribers."""
        return len(self._subscribers)