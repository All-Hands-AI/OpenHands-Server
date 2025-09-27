from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID

from openhands.sdk.event.types import EventID
from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.event_callback.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultPage,
    EventCallbackResultSortOrder,
)


_logger = logging.getLogger(__name__)


class EventCallbackResultService(ABC):
    """
    This service provides retrieval operations for event callback results available to
    the current user
    """

    @abstractmethod
    async def get_event_callback_result(self, id: UUID) -> EventCallbackResult | None:
        """Get a single event callback result, returning None if not found."""

    @abstractmethod
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
        """Search for event callback results, optionally filtered by
        callback_id, event_id or conversation_id, and sorting by created_at
        ascending or descending"""

    async def batch_get_event_callback_results(
        self, event_callback_result_ids: list[UUID]
    ) -> list[EventCallbackResult | None]:
        """Get a batch of event callback results, returning None for any
        result which was not found"""
        results = await asyncio.gather(
            *[
                self.get_event_callback_result(event_callback_result_id)
                for event_callback_result_id in event_callback_result_ids
            ]
        )
        return results

    @abstractmethod
    async def delete_event_callback_result(self, id: UUID) -> bool:
        """Delete an event callback result, returning True if deleted,
        False if not found."""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this service"""


class EventCallbackResultServiceResolver(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def get_unsecured_resolver(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of event callback result service.
        """

    @abstractmethod
    def get_resolver_for_user(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of event callback result service
        limited to the current user.
        """