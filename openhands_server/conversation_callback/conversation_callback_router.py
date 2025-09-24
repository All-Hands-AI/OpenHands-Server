"""Conversation Callback router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.conversation_callback.conversation_callback_context import (
    ConversationCallbackContext,
    get_conversation_callback_context_type,
)
from openhands_server.conversation_callback.conversation_callback_models import (
    ConversationCallback,
    ConversationCallbackPage,
)


router = APIRouter(prefix="/conversation-callbacks")
context_dependency = get_conversation_callback_context_type().with_instance

# Read methods


@router.get("/search")
async def search_conversation_callbacks(
    conversation_id: Annotated[
        UUID | None,
        Query(title="Optional filter by conversation ID"),
    ] = None,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> ConversationCallbackPage:
    """Search / List conversation callbacks."""
    assert limit > 0
    assert limit <= 100
    return await conversation_callback_context.search_conversation_callbacks(
        conversation_id=conversation_id, page_id=page_id, limit=limit
    )


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_conversation_callback(
    id: UUID,
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> ConversationCallback:
    """Get a single conversation callback given its id."""
    callback = await conversation_callback_context.get_conversation_callback(id)
    if callback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return callback


@router.get("/")
async def batch_get_conversation_callbacks(
    ids: Annotated[list[UUID], Query()],
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> list[ConversationCallback | None]:
    """Get a batch of conversation callbacks given their ids, returning null for any missing callback."""  # noqa: E501
    assert len(ids) <= 100
    callbacks = await conversation_callback_context.batch_get_conversation_callbacks(
        ids
    )
    return callbacks


# Write methods


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_conversation_callback(
    callback: ConversationCallback,
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> ConversationCallback:
    """Create a new conversation callback."""
    return await conversation_callback_context.create_conversation_callback(callback)


@router.put("/{id}", responses={404: {"description": "Item not found"}})
async def update_conversation_callback(
    id: UUID,
    callback: ConversationCallback,
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> ConversationCallback:
    """Update an existing conversation callback."""
    # Ensure the ID in the path matches the ID in the body
    callback.id = id
    updated_callback = await conversation_callback_context.update_conversation_callback(
        callback
    )
    if updated_callback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return updated_callback


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_conversation_callback(
    id: UUID,
    conversation_callback_context: ConversationCallbackContext = Depends(
        context_dependency
    ),
) -> dict[str, str]:
    """Delete a conversation callback."""
    deleted = await conversation_callback_context.delete_conversation_callback(id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {"message": "Conversation callback deleted successfully"}
