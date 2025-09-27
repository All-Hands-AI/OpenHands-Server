"""Event Callback router for OpenHands Server."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from openhands.agent_server.models import ConversationInfo
from openhands.sdk import EventBase
from openhands_server.dependency import get_dependency_resolver
from openhands_server.sandbox.sandbox_service import SandboxService


router = APIRouter(prefix="/event-webhooks", tags=["Event Callbacks"])
sandbox_service_dependency = Depends(
    get_dependency_resolver().sandbox.get_unsecured_resolver()
)

# TODO: I think we need a sandbox service (outside the context of the user)
#       where we can just load what we need


@router.post("/{sandbox_id}/conversations")
async def on_conversation_update(
    sandbox_id: str,
    conversation_info: ConversationInfo,
    session_api_key: str = Depends(
        APIKeyHeader(name="X-Session-API-Key", auto_error=False)
    ),
    sandbox_service: SandboxService = sandbox_service_dependency,
):
    """Webhook callback for when a conversation starts, pauses, resumes, or deletes"""

    # Check that the session api key is valid for the sandbox
    sandbox_info = await sandbox_service.get_sandbox(sandbox_id)
    if sandbox_info is None or sandbox_info.session_api_key != session_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

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
    sandbox_service: SandboxService = sandbox_service_dependency,
):
    """Webhook callback for when event stream events occur"""

    # Check that the session api key is valid for the sandbox
    sandbox_info = await sandbox_service.get_sandbox(sandbox_id)
    if sandbox_info is None or sandbox_info.session_api_key != session_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    # TODO: Load the sandbox and make sure that the session api key matches
    #       the one provided (Maybe use a dependency?)
    # TODO: Store each event
    # TODO: Invoke the callbacks for each event in background tasks.
