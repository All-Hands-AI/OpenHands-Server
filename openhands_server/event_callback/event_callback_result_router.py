"""Event Callback Result router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands.sdk.event.types import EventID
from openhands_server.dependency import get_dependency_resolver
from openhands_server.event_callback.event_callback_result_context import (
    EventCallbackResultContext,
)
from openhands_server.event_callback.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultPage,
    EventCallbackResultSortOrder,
)


router = APIRouter(prefix="/event-callback-results", tags=["Event Callbacks"])
event_callback_result_context_dependency = Depends(
    get_dependency_resolver().event_callback_result.get_resolver
)


# Read methods


@router.get("/search")
async def search_event_callback_results(
    event_callback_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by event callback ID"),
    ] = None,
    event_id__eq: Annotated[
        EventID | None,
        Query(title="Optional filter by event ID"),
    ] = None,
    conversation_id__eq: Annotated[
        UUID | None,
        Query(title="Optional filter by conversation ID"),
    ] = None,
    sort_order: Annotated[
        EventCallbackResultSortOrder,
        Query(title="Sort order for results"),
    ] = EventCallbackResultSortOrder.created_at,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    event_callback_result_context: EventCallbackResultContext = (
        event_callback_result_context_dependency
    ),
) -> EventCallbackResultPage:
    """Search / List event callback results."""
    assert limit > 0
    assert limit <= 100
    return await event_callback_result_context.search_event_callback_results(
        event_callback_id__eq=event_callback_id__eq,
        event_id__eq=event_id__eq,
        conversation_id__eq=conversation_id__eq,
        sort_order=sort_order,
        page_id=page_id,
        limit=limit,
    )


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_event_callback_result(
    id: UUID,
    event_callback_result_context: EventCallbackResultContext = (
        event_callback_result_context_dependency
    ),
) -> EventCallbackResult:
    """Get a single event callback result given its id."""
    result = await event_callback_result_context.get_event_callback_result(id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return result


@router.get("/")
async def batch_get_event_callback_results(
    ids: Annotated[list[UUID], Query()],
    event_callback_result_context: EventCallbackResultContext = (
        event_callback_result_context_dependency
    ),
) -> list[EventCallbackResult | None]:
    """Get a batch of event callback results given their ids, returning null for any
    missing result."""
    assert len(ids) <= 100
    results = await event_callback_result_context.batch_get_event_callback_results(ids)
    return results


# Write methods


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_event_callback_result(
    id: UUID,
    event_callback_result_context: EventCallbackResultContext = (
        event_callback_result_context_dependency
    ),
) -> dict[str, str]:
    """Delete an event callback result."""
    deleted = await event_callback_result_context.delete_event_callback_result(id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"message": "Event callback result deleted successfully"}
