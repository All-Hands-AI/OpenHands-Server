"""Event Callback router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.dependency import get_dependency_resolver
from openhands_server.event_callback.event_callback_context import (
    EventCallbackContext,
)
from openhands_server.event_callback.event_callback_models import (
    EventCallback,
    EventCallbackPage,
    EventKind,
)


router = APIRouter(prefix="/event-callbacks", tags=["Event Callbacks"])
event_callback_context_dependency = Depends(
    get_dependency_resolver().event_callback.get_resolver
)

# Read methods


@router.get("/search")
async def search_event_callbacks(
    conversation_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by conversation ID"),
    ] = None,
    event_kind__eq: Annotated[
        EventKind | None,
        Query(title="Optional filter by event kind"),
    ] = None,
    event_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by event ID"),
    ] = None,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    event_callback_context: EventCallbackContext = (event_callback_context_dependency),
) -> EventCallbackPage:
    """Search / List event callbacks."""
    assert limit > 0
    assert limit <= 100
    return await event_callback_context.search_event_callbacks(
        conversation_id__eq=conversation_id__eq,
        event_kind__eq=event_kind__eq,
        event_id__eq=event_id__eq,
        page_id=page_id,
        limit=limit,
    )


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_event_callback(
    id: UUID,
    event_callback_context: EventCallbackContext = (event_callback_context_dependency),
) -> EventCallback:
    """Get a single event callback given its id."""
    callback = await event_callback_context.get_event_callback(id)
    if callback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return callback


@router.get("/")
async def batch_get_event_callbacks(
    ids: Annotated[list[UUID], Query()],
    event_callback_context: EventCallbackContext = (event_callback_context_dependency),
) -> list[EventCallback | None]:
    """Get a batch of event callbacks given their ids, returning null for any missing
    callback."""
    assert len(ids) <= 100
    callbacks = await event_callback_context.batch_get_event_callbacks(ids)
    return callbacks


# Write methods


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_event_callback(
    callback: EventCallback,
    event_callback_context: EventCallbackContext = (event_callback_context_dependency),
) -> EventCallback:
    """Create a new event callback."""
    return await event_callback_context.create_event_callback(callback)


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_event_callback(
    id: UUID,
    event_callback_context: EventCallbackContext = (event_callback_context_dependency),
) -> dict[str, str]:
    """Delete a event callback."""
    deleted = await event_callback_context.delete_event_callback(id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"message": "Event callback deleted successfully"}
