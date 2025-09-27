"""Sandboxed Conversation router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.dependency import get_dependency_resolver
from openhands_server.sandboxed_conversation.sandboxed_conversation_models import (
    SandboxedConversationInfo,
    SandboxedConversationPage,
    StartSandboxedConversationRequest,
)
from openhands_server.sandboxed_conversation.sandboxed_conversation_service import (
    SandboxedConversationService,
)


router = APIRouter(prefix="/sandboxed-conversations")
sandboxed_conversation_service_dependency = Depends(
    get_dependency_resolver().sandboxed_conversation.get_resolver_for_user()
)

# Read methods


@router.get("/search")
async def search_sandboxed_conversations(
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
    sandboxed_conversation_service: SandboxedConversationService = (
        sandboxed_conversation_service_dependency
    ),
) -> SandboxedConversationPage:
    """Search / List sandboxed conversations"""
    assert limit > 0
    assert limit <= 100
    return await sandboxed_conversation_service.search_sandboxed_conversations(
        page_id, limit
    )


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandboxed_conversation(
    id: UUID,
    sandboxed_conversation_service: SandboxedConversationService = (
        sandboxed_conversation_service_dependency
    ),
) -> SandboxedConversationInfo:
    """Get a sandboxed conversation given an id"""
    sandboxed_conversation = (
        await sandboxed_conversation_service.get_sandboxed_conversation(id)
    )
    if sandboxed_conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandboxed_conversation


@router.get("/")
async def batch_get_sandboxed_conversations(
    ids: Annotated[list[UUID], Query()],
    sandboxed_conversation_service: SandboxedConversationService = (
        sandboxed_conversation_service_dependency
    ),
) -> list[SandboxedConversationInfo | None]:
    """Get a batch of sandboxed conversations given their ids, returning null for
    any missing spec."""
    assert len(ids) < 100
    sandboxed_conversations = (
        await sandboxed_conversation_service.batch_get_sandboxed_conversations(ids)
    )
    return sandboxed_conversations


@router.post("/")
async def start_sandboxed_conversation(
    request: StartSandboxedConversationRequest,
    sandboxed_conversation_service: SandboxedConversationService = (
        sandboxed_conversation_service_dependency
    ),
) -> SandboxedConversationInfo:
    return await sandboxed_conversation_service.start_sandboxed_conversation(request)
