"""Sandboxed Conversation router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
)
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import (
    get_default_sandboxed_conversation_service,
)
from openhands_server.user.user_dependencies import get_user_id


router = APIRouter(prefix="/sandboxed-conversations")
sandboxed_conversation_service = get_default_sandboxed_conversation_service()
router.lifespan(sandboxed_conversation_service)

# SandboxedConversations require user authentication and permissions
# All operations are scoped to the authenticated user

# Read methods


@router.get("/search")
async def search_sandboxed_conversations(
    user_id: Annotated[UUID, Depends(get_user_id)],
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(
            title="The max number of results in the page", gt=0, lte=100, default=100
        ),
    ] = 100,
) -> SandboxedConversationPage:
    """Search / List sandboxed conversations"""
    assert limit > 0
    assert limit <= 100
    return await sandboxed_conversation_service.search_sandboxed_conversations(
        user_id, page_id, limit
    )


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandboxed_conversation(
    id: UUID, user_id: Annotated[UUID, Depends(get_user_id)]
) -> SandboxedConversationInfo:
    """Get a sandboxed conversation given an id"""
    sandboxed_conversation = (
        await sandboxed_conversation_service.get_sandboxed_conversation(user_id, id)
    )
    if sandboxed_conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandboxed_conversation


@router.get("/")
async def batch_get_sandboxed_conversations(
    ids: Annotated[list[UUID], Query()], user_id: Annotated[UUID, Depends(get_user_id)]
) -> list[SandboxedConversationInfo | None]:
    """Get a batch of sandboxed conversations given their ids, returning null for any missing spec."""
    assert len(ids) < 100
    sandboxed_conversations = (
        await sandboxed_conversation_service.batch_get_sandboxed_conversations(
            user_id, ids
        )
    )
    return sandboxed_conversations
