"""User router for OpenHands Server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from openhands.agent_server.models import Success
from openhands_server.dependency import get_dependency_resolver
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
    UserSortOrder,
)
from openhands_server.user.user_service import UserService


router = APIRouter(prefix="/users", tags=["User"])
user_service_dependency = Depends(
    get_dependency_resolver().user.get_resolver_for_user()
)

# Read methods


@router.get("/search")
async def search_users(
    name__contains: Annotated[
        str | None,
        Query(title="Optional filter to search users by name containing this string"),
    ] = None,
    email__contains: Annotated[
        str | None,
        Query(title="Optional filter to search users by email containing this string"),
    ] = None,
    user_scopes__contains: Annotated[
        UserScope | None,
        Query(title="Optional filter to search users having this scope"),
    ] = None,
    sort_order: Annotated[
        UserSortOrder,
        Query(title="Sort order for the results"),
    ] = UserSortOrder.EMAIL,
    page_id: Annotated[
        str | None,
        Query(title="Optional next_page_id from the previously returned page"),
    ] = None,
    limit: Annotated[
        int,
        Query(title="The max number of results in the page", gt=0, lte=100),
    ] = 100,
    user_service: UserService = user_service_dependency,
) -> UserInfoPage:
    """Search / list users. Regular users can only see themselves, super admins can
    see all users."""
    assert limit > 0
    assert limit <= 100
    return await user_service.search_users(
        name__contains=name__contains,
        email__contains=email__contains,
        user_scopes__contains=user_scopes__contains,
        sort_order=sort_order,
        page_id=page_id,
        limit=limit,
    )


@router.get("/count")
async def count_users(
    name__contains: Annotated[
        str | None,
        Query(title="Optional filter to count users by name containing this string"),
    ] = None,
    email__contains: Annotated[
        str | None,
        Query(title="Optional filter to count users by email containing this string"),
    ] = None,
    user_scopes__contains: Annotated[
        UserScope | None,
        Query(title="Optional filter to count users having this scope"),
    ] = None,
    user_service: UserService = user_service_dependency,
) -> int:
    """Count users. Regular users can only see themselves, super admins can
    see all users."""
    return await user_service.count_users(
        name__contains=name__contains,
        email__contains=email__contains,
        user_scopes__contains=user_scopes__contains,
    )


@router.get("/me")
async def get_current_user(
    user_service: UserService = user_service_dependency,
) -> UserInfo:
    """Get the current authenticated user."""
    user = await user_service.get_current_user()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.get("/{id}", responses={404: {"description": "Item not found"}})
async def get_user(
    id: str,
    user_service: UserService = user_service_dependency,
) -> UserInfo:
    """Get a single user given an id. Users can only see themselves unless
    they're super admin."""
    user = await user_service.get_user(id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return user


@router.get("/")
async def batch_get_users(
    ids: Annotated[list[str], Query()],
    user_service: UserService = user_service_dependency,
) -> list[UserInfo | None]:
    """Get a batch of users given their ids, returning null for any missing
    user. Users can only see themselves unless they're super admin."""
    assert len(ids) < 100
    users = await user_service.batch_get_users(ids)
    return users


# Write Methods


@router.post("/")
async def create_user(
    request: CreateUserRequest,
    user_service: UserService = user_service_dependency,
) -> UserInfo:
    """Create a new user. Only super admins can create users."""
    try:
        user = await user_service.create_user(request)
        return user
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/{id}", responses={404: {"description": "Item not found"}})
async def update_user(
    id: str,
    request: UpdateUserRequest,
    user_service: UserService = user_service_dependency,
) -> UserInfo:
    """Update a user. Users can update themselves, super admins can update anyone."""
    # Ensure the ID in the path matches the ID in the request
    request.id = id

    try:
        user = await user_service.update_user(request)
        return user
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{id}", responses={404: {"description": "Item not found"}})
async def delete_user(
    id: str,
    user_service: UserService = user_service_dependency,
) -> Success:
    """Delete a user. Only super admins can delete users."""
    try:
        exists = await user_service.delete_user(id)
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return Success()
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
