"""User router for OpenHands Server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands_server.user.models import Success
from openhands_server.dependency import get_dependency_resolver
from openhands_server.user.user_context import UserContext
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
)


router = APIRouter(prefix="/users", tags=["User"])
user_context_dependency = Depends(get_dependency_resolver().user.get_resolver())

# Read methods


@router.get("/search")
async def search_users(
    created_by_user_id__eq: Annotated[
        str | None,
        Query(title="Optional id of the user who created the user"),
    ] = None,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    user_context: UserContext = user_context_dependency,
) -> UserInfoPage:
    """Search / list users. Regular users can only see themselves, super admins can see all users."""
    assert limit > 0
    assert limit <= 100
    return await user_context.search_users(
        created_by_user_id__eq=created_by_user_id__eq, page_id=page_id, limit=limit
    )


@router.get("/me")
async def get_current_user(
    user_context: UserContext = user_context_dependency,
) -> UserInfo:
    """Get the current authenticated user."""
    user = await user_context.get_current_user()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_user(
    id: str,
    user_context: UserContext = user_context_dependency,
) -> UserInfo:
    """Get a single user given an id. Users can only see themselves unless they're super admin."""
    user = await user_context.get_user(id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


@router.get("/")
async def batch_get_users(
    ids: Annotated[list[str], Query()],
    user_context: UserContext = user_context_dependency,
) -> list[UserInfo | None]:
    """Get a batch of users given their ids, returning null for any missing
    user. Users can only see themselves unless they're super admin."""
    assert len(ids) < 100
    users = await user_context.batch_get_users(ids)
    return users


# Write Methods


@router.post("/")
async def create_user(
    request: CreateUserRequest,
    user_context: UserContext = user_context_dependency,
) -> UserInfo:
    """Create a new user. Only super admins can create users."""
    try:
        user = await user_context.create_user(request)
        return user
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/{id}", responses={404: {"description": "Item not found"}})
async def update_user(
    id: str,
    request: UpdateUserRequest,
    user_context: UserContext = user_context_dependency,
) -> UserInfo:
    """Update a user. Users can update themselves, super admins can update anyone."""
    # Ensure the ID in the path matches the ID in the request
    request.id = id
    
    try:
        user = await user_context.update_user(request)
        return user
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_user(
    id: str,
    user_context: UserContext = user_context_dependency,
) -> Success:
    """Delete a user. Only super admins can delete users."""
    try:
        exists = await user_context.delete_user(id)
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return Success()
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))