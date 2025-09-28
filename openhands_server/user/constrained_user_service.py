"""Constrained User Service - Security wrapper for UserService implementations.

This module provides a security wrapper that enforces access control and permission
checks around any UserService implementation. It separates security concerns from
the core data access logic, allowing the underlying service to focus purely on
data operations while this wrapper handles:

- SUPER_ADMIN scope validation
- Self-access restrictions for regular users
- Permission checks for user creation, updates, and deletion
- Scope assignment validation

The ConstrainedUserService can wrap any UserService implementation, making it
reusable across different data storage backends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openhands_server.errors import AuthError
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
    UserSortOrder,
)
from openhands_server.user.user_service import UserService


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ConstrainedUserService(UserService):
    """Security wrapper for UserService implementations.

    This class wraps any UserService implementation and enforces security
    constraints and permission checks. It implements the same UserService
    interface, making it a drop-in replacement that adds security.
    """

    wrapped_service: UserService
    current_user_id: str

    async def get_current_user(self) -> UserInfo | None:
        """Get the current user."""
        return await self.wrapped_service.get_user(self.current_user_id)

    async def search_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
        sort_order: UserSortOrder = UserSortOrder.EMAIL,
        page_id: str | None = None,
        limit: int = 100,
    ) -> UserInfoPage:
        """Search for users with security constraints."""
        # Check if current user has permission to search users
        current_user = await self.get_current_user()
        if current_user is None:
            raise AuthError("Not logged in!")
        if UserScope.SUPER_ADMIN not in current_user.user_scopes:
            # Regular users can only see themselves
            if (
                _contains(name__contains, current_user.name)
                and _contains(email__contains, current_user.email)
                and _contains(user_scopes__contains, current_user.user_scopes)
            ):
                return UserInfoPage(items=[current_user], next_page_id=None)

            return UserInfoPage(items=[], next_page_id=None)

        # Super admin can search all users - delegate to wrapped service
        return await self.wrapped_service.search_users(
            name__contains=name__contains,
            email__contains=email__contains,
            user_scopes__contains=user_scopes__contains,
            sort_order=sort_order,
            page_id=page_id,
            limit=limit,
        )

    async def count_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
    ) -> int:
        """Search for users with security constraints."""
        # Check if current user has permission to search users
        current_user = await self.get_current_user()
        if current_user is None:
            raise AuthError("Not logged in!")
        if UserScope.SUPER_ADMIN not in current_user.user_scopes:
            # Regular users can only see themselves
            if (
                _contains(name__contains, current_user.name)
                and _contains(email__contains, current_user.email)
                and _contains(user_scopes__contains, current_user.user_scopes)
            ):
                return 1

            return 0

        # Super admin can search all users - delegate to wrapped service
        return await self.wrapped_service.count_users(
            name__contains=name__contains,
            email__contains=email__contains,
            user_scopes__contains=user_scopes__contains,
        )

    async def get_user(self, id: str) -> UserInfo | None:
        """Get a single user with permission checks."""
        # Check permissions - users can only see themselves unless they're super admin
        current_user = await self.get_current_user()
        if (
            current_user is not None
            and UserScope.SUPER_ADMIN not in current_user.user_scopes
            and current_user.id != id
        ):
            return None

        # Permission check passed - delegate to wrapped service
        return await self.wrapped_service.get_user(id)

    async def create_user(self, request: CreateUserRequest) -> UserInfo:
        """
        Create a user with permission validation.

        Raises:
            PermissionError: If current user lacks permission to create users
                           or grant the requested scopes
        """
        # Check if current user has permission to create users
        current_user = await self.get_current_user()
        if (
            current_user is None
            or UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            raise PermissionError("Only super admins can create users")

        # Permission checks passed - delegate to wrapped service
        return await self.wrapped_service.create_user(request)

    async def update_user(self, request: UpdateUserRequest) -> UserInfo:
        """
        Update a user with permission validation.

        Raises:
            PermissionError: If current user lacks permission to update the user
                           or grant the requested scopes
            ValueError: If the user to update is not found
        """
        # Check permissions
        current_user = await self.get_current_user()
        if current_user is None:
            raise PermissionError("Authentication required")

        # Users can update themselves, super admins can update anyone
        if (
            current_user.id != request.id
            and UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            raise PermissionError("You can only update your own profile")

        # Check if user exists (delegate to wrapped service for existence check)
        existing_user = await self.wrapped_service.get_user(request.id)
        if existing_user is None:
            raise ValueError(f"User with id {request.id} not found")

        # Check scope permissions
        if UserScope.SUPER_ADMIN in request.user_scopes:
            # Only super admins can grant super admin privileges
            if UserScope.SUPER_ADMIN not in current_user.user_scopes:
                raise PermissionError(
                    "Only super admins can grant super admin privileges"
                )

        # Permission checks passed - delegate to wrapped service
        return await self.wrapped_service.update_user(request)

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete a user with permission validation.

        Raises:
            PermissionError: If current user lacks permission to delete users
        """
        # Check if current user has permission to delete users
        current_user = await self.get_current_user()
        if (
            current_user is None
            or UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            raise PermissionError("Only super admins can delete users")

        # Permission check passed - delegate to wrapped service
        return await self.wrapped_service.delete_user(user_id)


def _contains(query, value):
    if not query:
        return True
    if not value:
        return False
    return query in value
