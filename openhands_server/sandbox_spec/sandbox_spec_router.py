"""Runtime Images router for OpenHands Server."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from openhands_server.sandbox_spec.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)
from openhands_server.sandbox_spec.sandbox_spec_service import (
    SandboxSpecService,
    get_default_sandbox_spec_service,
)


router = APIRouter(prefix="/runtime-images")
sandbox_spec_service: SandboxSpecService = get_default_sandbox_spec_service()
router.lifespan(sandbox_spec_service)

# Read methods


@router.get("/search")
async def search_sandbox_specs(
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
) -> SandboxSpecInfoPage:
    """Search / List sandbox specs."""
    assert limit > 0
    assert limit <= 100
    return await sandbox_spec_service.search_sandbox_specs(page_id=page_id, limit=limit)


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_sandbox_spec(id: UUID) -> SandboxSpecInfo:
    """Get a single sandbox spec given its id."""
    sandbox_specs = await sandbox_spec_service.get_sandbox_spec(id)
    if sandbox_specs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return sandbox_specs


@router.get("/")
async def batch_get_sandbox_specs(ids: Annotated[list[UUID], Query()]) -> list[SandboxSpecInfo | None]:
    """Get a batch of sandbox specs given their ids, returning null for any missing spec."""
    assert len(ids) <= 100
    sandbox_specss = await sandbox_spec_service.batch_get_sandbox_specs(ids)
    return sandbox_specss
