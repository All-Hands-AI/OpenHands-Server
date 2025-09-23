"""Runtime Containers router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage
from openhands_server.sandbox.sandbox_service import (
    SandboxService,
    get_default_sandbox_service,
)
from openhands_server.sandbox_spec.sandbox_spec_router import sandbox_spec_service
from openhands_server.user.user_context import UserContext
from openhands_server.user.user_dependencies import get_user_context, get_user_id
from openhands_server.utils.success import Success


router = APIRouter(prefix="/sandbox-containers")
sandbox_service: SandboxService = get_default_sandbox_service()
router.lifespan(sandbox_service)

# TODO: Currently a sandbox is only available to the user who created it. In future we could have a more advanced permissions model for sharing

# Read methods


@router.get("/search")
async def search_sandboxes(
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
    user_id: UUID = Depends(get_user_id),
) -> SandboxPage:
    """Search / list sandboxes owned by the current user."""
    assert limit > 0
    assert limit <= 100
    return await sandbox_service.search_sandboxes(user_id, page_id, limit)


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandbox(id: UUID, user_id: UUID = Depends(get_user_id)) -> SandboxInfo:
    """Get a single sandbox given an id"""
    sandbox = await sandbox_service.get_sandbox(id)
    if sandbox is None or sandbox.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandbox


@router.get("/")
async def batch_get_sandboxes(
    ids: Annotated[list[UUID], Query()],
    user_id: UUID = Depends(get_user_id),
) -> list[SandboxInfo | None]:
    """Get a batch of sandboxes given their ids, returning null for any missing sandbox."""
    assert len(ids) < 100
    sandboxes = await sandbox_service.batch_get_sandboxes(user_id, ids)
    sandboxes = [
        sandbox if sandbox and sandbox.user_id == user_id else None
        for sandbox in sandboxes
    ]
    return sandboxes


# Write Methods


@router.post("/")
async def start_sandbox(
    sandbox_spec_id: str | None = None,
    user_context: UserContext = Depends(get_user_context),
) -> SandboxInfo:
    sandbox_spec = await sandbox_spec_service.get_default_sandbox_spec()
    info = await sandbox_service.start_sandbox(user_context, sandbox_spec.id)
    return info


@router.post("/{id}/pause", responses={404: {"description": "Item not found"}})
async def pause_sandbox(id: UUID, user_id: UUID = Depends(get_user_id)) -> Success:
    exists = await sandbox_service.pause_sandbox(user_id, id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.post("/{id}/resume", responses={404: {"description": "Item not found"}})
async def resume_sandbox(id: UUID, user_id: UUID = Depends(get_user_id)) -> Success:
    exists = await sandbox_service.resume_sandbox(user_id, id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_sandbox(id: UUID, user_id: UUID = Depends(get_user_id)) -> Success:
    exists = await sandbox_service.delete_sandbox(user_id, id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()
