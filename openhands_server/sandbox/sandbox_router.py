"""Runtime Containers router for OpenHands Server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands.agent_server.models import Success
from openhands_server.dependency import get_dependency_resolver
from openhands_server.sandbox.sandbox_context import (
    SandboxContext,
)
from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage


router = APIRouter(prefix="/sandboxes", tags=["Sandbox"])
sandbox_context_dependency = Depends(get_dependency_resolver().sandbox.get_resolver())

# Read methods


@router.get("/search")
async def search_sandboxes(
    created_by_user_id__eq: Annotated[
        str | None,
        Query(title="Optional id of the user who created the sandbox"),
    ] = None,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> SandboxPage:
    """Search / list sandboxes owned by the current user."""
    assert limit > 0
    assert limit <= 100
    return await sandbox_context.search_sandboxes(
        created_by_user_id__eq=created_by_user_id__eq, page_id=page_id, limit=limit
    )


@router.get("/{sandbox_id}", responses={404: {"description": "Item not found"}})
async def get_sandbox(
    id: str,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> SandboxInfo:
    """Get a single sandbox given an id"""
    sandbox = await sandbox_context.get_sandbox(id)
    if sandbox is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandbox


@router.get("/")
async def batch_get_sandboxes(
    sandbox_ids: Annotated[list[str], Query()],
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> list[SandboxInfo | None]:
    """Get a batch of sandboxes given their ids, returning null for any missing
    sandbox."""
    assert len(sandbox_ids) < 100
    sandboxes = await sandbox_context.batch_get_sandboxes(sandbox_ids)
    return sandboxes


# Write Methods


@router.post("/")
async def start_sandbox(
    sandbox_spec_id: str | None = None,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> SandboxInfo:
    info = await sandbox_context.start_sandbox(sandbox_spec_id)
    return info


@router.post("/{id}/pause", responses={404: {"description": "Item not found"}})
async def pause_sandbox(
    sandbox_id: str,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> Success:
    exists = await sandbox_context.pause_sandbox(sandbox_id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.post("/{id}/resume", responses={404: {"description": "Item not found"}})
async def resume_sandbox(
    sandbox_id: str,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> Success:
    exists = await sandbox_context.resume_sandbox(sandbox_id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_sandbox(
    sandbox_id: str,
    sandbox_context: SandboxContext = sandbox_context_dependency,
) -> Success:
    exists = await sandbox_context.delete_sandbox(sandbox_id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Success()
