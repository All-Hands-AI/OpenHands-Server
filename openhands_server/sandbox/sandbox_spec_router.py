"""Runtime Images router for OpenHands Server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.dependency import get_dependency_resolver
from openhands_server.sandbox.sandbox_spec_context import (
    SandboxSpecContext,
)
from openhands_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)


router = APIRouter(prefix="/sandbox-specs", tags=["Sandbox"])
sandbox_spec_context_dependency = Depends(
    get_dependency_resolver().event_callback.get_resolver()
)


# Read methods


@router.get("/search")
async def search_sandbox_specs(
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    sandbox_spec_context: SandboxSpecContext = sandbox_spec_context_dependency,
) -> SandboxSpecInfoPage:
    """Search / List sandbox specs."""
    assert limit > 0
    assert limit <= 100
    return await sandbox_spec_context.search_sandbox_specs(page_id=page_id, limit=limit)


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandbox_spec(
    id: str,
    sandbox_spec_context: SandboxSpecContext = sandbox_spec_context_dependency,
) -> SandboxSpecInfo:
    """Get a single sandbox spec given its id."""
    sandbox_spec = await sandbox_spec_context.get_sandbox_spec(id)
    if sandbox_spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandbox_spec


@router.get("/")
async def batch_get_sandbox_specs(
    ids: Annotated[list[str], Query()],
    sandbox_spec_context: SandboxSpecContext = sandbox_spec_context_dependency,
) -> list[SandboxSpecInfo | None]:
    """Get a batch of sandbox specs given their ids, returning null for any missing
    spec."""
    assert len(ids) <= 100
    sandbox_specs = await sandbox_spec_context.batch_get_sandbox_specs(ids)
    return sandbox_specs
