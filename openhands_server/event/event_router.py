"""Event router for OpenHands Server."""

from typing import Annotated
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.agent_server.models import EventPage, EventSortOrder
from openhands.sdk import EventBase
from openhands_server.event.event_context import (
    EventContext,
    get_event_context_type,
)
from openhands_server.event_callback.event_callback_models import EventKind


router = APIRouter(prefix="/events", tags=["Events"])
context_dependency = get_event_context_type().with_instance

# Read methods


@router.get("/search")
async def search_events(
    conversation_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by conversation ID"),
    ] = None,
    kind__eq: Annotated[
        EventKind | None,
        Query(title="Optional filter by event kind"),
    ] = None,
    timestamp__gte: Annotated[
        datetime | None,
        Query(title="Optional filter by timestamp greater than or equal to"),
    ] = None,
    timestamp__lt: Annotated[
        datetime | None,
        Query(title="Optional filter by timestamp less than"),
    ] = None,
    sort_order: Annotated[
        EventSortOrder,
        Query(title="Sort order for results"),
    ] = EventSortOrder.TIMESTAMP,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    event_context: EventContext = Depends(context_dependency),
) -> EventPage:
    """Search / List events."""
    assert limit > 0
    assert limit <= 100
    return await event_context.search_events(
        conversation_id__eq=conversation_id__eq,
        kind__eq=kind__eq,
        timestamp__gte=timestamp__gte,
        timestamp__lt=timestamp__lt,
        sort_order=sort_order,
        page_id=page_id,
        limit=limit,
    )


@router.get("/count")
async def count_events(
    conversation_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by conversation ID"),
    ] = None,
    kind__eq: Annotated[
        EventKind | None,
        Query(title="Optional filter by event kind"),
    ] = None,
    timestamp__gte: Annotated[
        datetime | None,
        Query(title="Optional filter by timestamp greater than or equal to"),
    ] = None,
    timestamp__lt: Annotated[
        datetime | None,
        Query(title="Optional filter by timestamp less than"),
    ] = None,
    sort_order: Annotated[
        EventSortOrder,
        Query(title="Sort order for results"),
    ] = EventSortOrder.TIMESTAMP,
    event_context: EventContext = Depends(context_dependency),
) -> int:
    """Count events matching the given filters."""
    return await event_context.count_events(
        conversation_id__eq=conversation_id__eq,
        kind__eq=kind__eq,
        timestamp__gte=timestamp__gte,
        timestamp__lt=timestamp__lt,
        sort_order=sort_order,
    )


@router.get("/{event_id}", responses={404: {"description": "Item not found"}})
async def get_event(
    event_id: str,
    event_context: EventContext = Depends(context_dependency),
) -> EventBase:
    """Get a single event given its id."""
    event = await event_context.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@router.get("/")
async def batch_get_events(
    event_ids: Annotated[list[str], Query()],
    event_context: EventContext = Depends(context_dependency),
) -> list[EventBase | None]:
    """Get a batch of events given their ids, returning null for any missing event."""
    assert len(event_ids) <= 100
    events = await event_context.batch_get_events(event_ids)
    return events