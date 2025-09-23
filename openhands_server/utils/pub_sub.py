from dataclasses import dataclass, field
from uuid import UUID

from openhands.sdk.event import Event
from openhands.sdk.logger import get_logger
from openhands.sdk.utils.async_utils import AsyncConversationCallback


logger = get_logger(__name__)


@dataclass
class PubSub:
    """A subscription service that extends ConversationCallbackType functionality.
    This class maintains a dictionary of UUIDs to ConversationCallbackType instances
    and provides methods to subscribe/unsubscribe callbacks. When invoked, it calls
    all registered callbacks with proper error handling.
    """

    _callbacks: dict[UUID, AsyncConversationCallback] = field(default_factory=dict)

    def subscribe(self, callback: AsyncConversationCallback) -> UUID:
        """Subscribe a callback and return its UUID for later unsubscription.
        Args:
            callback: The callback function to register
        Returns:
            str: UUID that can be used to unsubscribe this callback
        """
        callback_id = uuid4()
        self._callbacks[callback_id] = callback
        logger.debug(f"Subscribed callback with ID: {callback_id}")
        return callback_id

    def unsubscribe(self, callback_id: UUID) -> bool:
        """Unsubscribe a callback by its UUID.
        Args:
            callback_id: The UUID returned by subscribe()
        Returns:
            bool: True if callback was found and removed, False otherwise
        """
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]
            logger.debug(f"Unsubscribed callback with ID: {callback_id}")
            return True
        else:
            logger.warning(
                f"Attempted to unsubscribe unknown callback ID: {callback_id}"
            )
            return False

    async def __call__(self, event: Event) -> None:
        """Invoke all registered callbacks with the given event.
        Each callback is invoked in its own try/catch block to prevent
        one failing callback from affecting others.
        Args:
            event: The event to pass to all callbacks
        """
        for callback_id, callback in self._callbacks.items():
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback {callback_id}: {e}", exc_info=True)

    def on_event(self, event: Event) -> None:
        """Alias for __call__ method.
        Args:
            event: The event to pass to all callbacks
        """
        self(event)

    @property
    def callback_count(self) -> int:
        """Return the number of registered callbacks."""
        return len(self._callbacks)

    def clear(self) -> None:
        """Remove all registered callbacks."""
        count = len(self._callbacks)
        self._callbacks.clear()
        logger.debug(f"Cleared {count} callbacks")
