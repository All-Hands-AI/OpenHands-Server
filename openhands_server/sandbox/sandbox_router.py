"""Runtime Containers router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands.agent_server.models import Success
from openhands_server.sandbox.sandbox_context import (
    SandboxContext,
    sandbox_context_dependency,
)
from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage


router = APIRouter(prefix="/sandboxes", tags=["Sandbox"])

# TODO: Currently a sandbox is only available to the user who created it. In
# future we could have a more advanced permissions model for sharing

# Read methods


@router.get("/search")
async def search_sandboxes(
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> SandboxPage:
    """Search / list sandboxes owned by the current user."""
    assert limit > 0
    assert limit <= 100
    return await sandbox_context.search_sandboxes(page_id, limit)


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandbox(
    id: UUID,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> SandboxInfo:
    """Get a single sandbox given an id"""
    sandbox = await sandbox_context.get_sandbox(id)
    if sandbox is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandbox


@router.get("/")
async def batch_get_sandboxes(
    ids: Annotated[list[UUID], Query()],
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> list[SandboxInfo | None]:
    """Get a batch of sandboxes given their ids, returning null for any missing
    sandbox."""
    assert len(ids) < 100
    sandboxes = await sandbox_context.batch_get_sandboxes(ids)
    return sandboxes


# Write Methods


@router.post("/")
async def start_sandbox(
    sandbox_spec_id: str | None = None,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> SandboxInfo:
    info = await sandbox_context.start_sandbox(sandbox_spec_id)
    return info


@router.post("/{id}/pause", responses={404: {"description": "Item not found"}})
async def pause_sandbox(
    id: UUID,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> Success:
    exists = await sandbox_context.pause_sandbox(id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.post("/{id}/resume", responses={404: {"description": "Item not found"}})
async def resume_sandbox(
    id: UUID,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> Success:
    exists = await sandbox_context.resume_sandbox(id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_sandbox(
    id: UUID,
    sandbox_context: SandboxContext = Depends(sandbox_context_dependency),
) -> Success:
    exists = await sandbox_context.delete_sandbox(id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()
