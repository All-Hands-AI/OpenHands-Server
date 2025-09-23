"""
Local Conversation router for OpenHands Server. Local Conversations rely on a single sesison api key
for validation
"""

import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.websockets import WebSocketState

from openhands.sdk import EventBase, Message
from openhands_server.local_conversation.local_conversation_models import (
    LocalConversationPage,
)
from openhands_server.local_conversation.local_conversation_service import (
    get_default_local_conversation_service,
)
from openhands_server.utils.success import Success


router = APIRouter(prefix="/local-conversations/{conversation_id}/events")
local_conversation_service = get_default_local_conversation_service()
logger = logging.getLogger(__name__)

# LocalConversations are not available in the outer nesting container. They do not currently have permissions
# as all validation is through the session_api_key

# Read methods


@router.get("/search", responses={404: {"description": "Conversation not found"}})
async def search_local_conversation_events(
    conversation_id: UUID,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
) -> LocalConversationPage:
    """Search / List local events"""
    assert limit > 0
    assert limit <= 100
    event_context = await local_conversation_service.get_event_context(conversation_id)
    if event_context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return await event_context.search(page_id, limit)


@router.get("/{event_id}", responses={404: {"description": "Item not found"}})
async def get_local_conversation_event(
    conversation_id: UUID, event_id: UUID
) -> EventBase:
    """Get a local conversation given an id"""
    event_context = await local_conversation_service.get_event_context(conversation_id)
    if event_context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    event = event_context.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return event


@router.get("/")
async def batch_get_local_conversation_events(
    conversation_id: UUID, event_ids: list[UUID]
) -> list[EventBase | None]:
    """Get a batch of local conversations given their ids, returning null for any missing spec."""
    event_context = await local_conversation_service.get_event_context(conversation_id)
    if event_context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    events = await event_context.batch_get_events(event_ids)
    return events


# Write Methods


@router.post("/")
async def send_message(conversation_id: UUID, message: Message) -> Success:
    """Start a local conversation"""
    event_context = await local_conversation_service.get_event_context(conversation_id)
    if event_context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await event_context.send_message(message)
    return Success()


@router.websocket("/socket")
async def socket(
    conversation_id: UUID,
    websocket: WebSocket,
):
    await websocket.accept()
    event_context = await local_conversation_service.get_event_context(conversation_id)
    if event_context is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    subscriber_id = event_context.subscribe_to_events(_WebSocketSubscriber(websocket))
    try:
        while websocket.application_state == WebSocketState.CONNECTED:
            try:
                data = await websocket.receive_json()
                message = Message.model_validate(data)
                await event_context.send_message(message)
            except WebSocketDisconnect:
                event_context.unsubscribe_from_events(subscriber_id)
            except Exception:
                logger.exception("error_in_subscription", stack_info=True)
    finally:
        await event_context.unsubscribe_from_events(subscriber_id)


@dataclass
class _WebSocketSubscriber:
    websocket: WebSocket

    async def __call__(self, event: EventBase):
        try:
            json_str = event.model_dump_json()
            self.websocket.send(json_str)
        except Exception:
            logger.exception("error_sending_event:{event}", stack_info=True)
