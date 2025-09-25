"""Event Callback router for OpenHands Server."""

from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader

from openhands.agent_server.models import ConversationInfo
from openhands.sdk import EventBase


router = APIRouter(prefix="/event-webhooks", tags=["Event Callbacks"])


# TODO: We need to put into the runtime the correct url for callbacks


@router.post("/{sandbox_id}/conversations")
async def on_conversation_update(
    sandbox_id: str,
    conversation_info: ConversationInfo,
    session_api_key: str = Depends(
        APIKeyHeader(name="X-Session-API-Key", auto_error=False)
    ),
):
    """Webhook callback for when a conversation starts, pauses, resumes, or deletes"""
    # TODO: Load the sandbox and make sure that the session api key matches
    #       the one provided (Maybe use a dependency?)
    # TODO: Make sure that we have an entry saved for the conversation info.
    #       (We will still go back to the sandbox to determine its status,
    #       but we want the metrics.)


@router.post("/{sandbox_id}/events")
async def on_event(
    sandbox_id: str,
    events: list[EventBase],
    session_api_key: str = Depends(
        APIKeyHeader(name="X-Session-API-Key", auto_error=False)
    ),
):
    """Webhook callback for when event stream events occur"""
    # TODO: Load the sandbox and make sure that the session api key matches
    #       the one provided (Maybe use a dependency?)
    # TODO: Store each event
    # TODO: Invoke the callbacks for each event in background tasks.
