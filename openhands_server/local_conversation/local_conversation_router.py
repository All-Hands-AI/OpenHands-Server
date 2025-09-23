"""Local Conversation router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from openhands_server.local_conversation.local_conversation_models import (
    ConfirmationResponseRequest,
    LocalConversationInfo,
    LocalConversationPage,
    SendMessageRequest,
    StartLocalConversationRequest,
)
from openhands_server.local_conversation.local_conversation_service import (
    get_default_local_conversation_service,
)
from openhands_server.utils.success import Success


router = APIRouter(prefix="/local-conversations")
local_conversation_service = get_default_local_conversation_service()

# LocalConversations are not available in the outer nesting container. They do not currently have permissions
# as all validation is through the session_api_key

# Read methods


@router.get("/search")
async def search_local_conversations(
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
) -> LocalConversationPage:
    """Search / List local conversations"""
    assert limit > 0
    assert limit <= 100
    return await local_conversation_service.search_local_conversations(page_id, limit)


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_local_conversation(id: UUID) -> LocalConversationInfo:
    """Get a local conversation given an id"""
    local_conversation = await local_conversation_service.get_local_conversation(id)
    if local_conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return local_conversation


@router.get("/")
async def batch_get_local_conversations(
    ids: Annotated[list[UUID], Query()],
) -> list[LocalConversationInfo | None]:
    """Get a batch of local conversations given their ids, returning null for any missing spec."""
    assert len(ids) < 100
    local_conversations = (
        await local_conversation_service.batch_get_local_conversations(ids)
    )
    return local_conversations


# Write Methods


@router.post("/")
async def start_local_conversation(
    request: StartLocalConversationRequest,
) -> LocalConversationInfo:
    """Start a local conversation"""
    info = await local_conversation_service.start_local_conversation(request)
    return info


@router.post("/{id}/pause", responses={404: {"description": "Item not found"}})
async def pause_local_conversation(id: UUID) -> Success:
    paused = await local_conversation_service.pause_local_conversation(id)
    if not paused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@router.post("/{id}/resume", responses={404: {"description": "Item not found"}})
async def resume_local_conversation(id: UUID) -> Success:
    paused = await local_conversation_service.resume_local_conversation(id)
    if not paused:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_local_conversation(id: UUID) -> Success:
    deleted = await local_conversation_service.delete_local_conversation(id)
    if not deleted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST)
    return Success()


@router.post("/{id}/messages", responses={404: {"description": "Item not found"}})
async def send_message_to_conversation(id: UUID, request: SendMessageRequest) -> Success:
    """Send a message to a conversation and optionally run it."""
    sent = await local_conversation_service.send_message_to_conversation(id, request)
    if not sent:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.post("/{id}/respond_to_confirmation", responses={404: {"description": "Item not found"}})
async def respond_to_confirmation(id: UUID, request: ConfirmationResponseRequest) -> Success:
    """Accept or reject a pending action in confirmation mode."""
    responded = await local_conversation_service.respond_to_confirmation(id, request)
    if not responded:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()
