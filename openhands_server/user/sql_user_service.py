# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
"""SQL implementation of UserService.

This implementation provides CRUD operations for users with the following features:
- Permission-based access control (regular users can only see/modify themselves)
- Super admin users can manage all users and create other users
- Proper validation of user scopes and permissions
- Pagination support for user search
- Full async/await support using SQL async sessions

Key components:
- SQLUserService: Main service class implementing all CRUD operations
- SQLUserServiceResolver: Dependency injection resolver for FastAPI
- StoredUser: Database model with proper Pydantic conversion methods
"""

from __future__ import annotations

import logging
from typing import Callable

import base62
from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.database import async_session_dependency
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
)
from openhands_server.user.user_service import UserService, UserServiceResolver
from openhands_server.utils.date_utils import utc_now


logger = logging.getLogger(__name__)


class SQLUserService(UserService):
    """SQL implementation of UserService."""

    def __init__(self, session: AsyncSession, current_user_id: str | None = None):
        """
        Initialize the SQL user service.

        Args:
            session: The async SQL session
            current_user_id: The ID of the current user (for permission checks)
        """
        self.session = session
        self.current_user_id = current_user_id

    async def get_current_user(self) -> UserInfo | None:
        """Get the current user."""
        if self.current_user_id is None:
            return None

        return await self.get_user(self.current_user_id)

    async def search_users(
        self,
        created_by_user_id__eq: str | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> UserInfoPage:
        """Search for users."""
        # Check if current user has permission to search users
        current_user = await self.get_current_user()
        if (
            current_user is None
            or UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            # Regular users can only see themselves
            if self.current_user_id is None:
                return UserInfoPage(items=[], next_page_id=None)

            user = await self.get_user(self.current_user_id)
            if user is None:
                return UserInfoPage(items=[], next_page_id=None)

            return UserInfoPage(items=[user], next_page_id=None)

        # Super admin can search all users
        query = select(UserInfo)

        # Apply filters
        conditions = []
        if created_by_user_id__eq is not None:
            # Note: We don't have a created_by_user_id field in the user model
            # This filter is included for API compatibility but won't filter anything
            pass

        if conditions:
            query = query.where(and_(*conditions))

        # Apply pagination
        if page_id is not None:
            try:
                offset = int(page_id)
                query = query.offset(offset)
            except ValueError:
                # If page_id is not a valid integer, start from beginning
                offset = 0
        else:
            offset = 0

        # Apply limit and get one extra to check if there are more results
        query = query.limit(limit + 1).order_by(UserInfo.created_at.desc())

        result = await self.session.execute(query)
        stored_users = list(result.scalars().all())

        # Check if there are more results
        has_more = len(stored_users) > limit
        if has_more:
            stored_users = stored_users[:limit]

        # Calculate next page ID
        next_page_id = None
        if has_more:
            next_page_id = str(offset + limit)

        return UserInfoPage(items=stored_users, next_page_id=next_page_id)

    async def get_user(self, id: str) -> UserInfo | None:
        """Get a single user. Return None if the user was not found."""
        # Check permissions - users can only see themselves unless they're super admin
        current_user = await self._get_current_user_without_recursion()
        if (
            current_user is not None
            and UserScope.SUPER_ADMIN not in current_user.user_scopes
            and current_user.id != id
        ):
            return None

        query = select(UserInfo).where(UserInfo.id == id)
        result = await self.session.execute(query)
        stored_user = result.scalar_one_or_none()
        return stored_user

    async def create_user(self, request: CreateUserRequest) -> UserInfo:
        """
        Create a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to create users or grant the requested
        scopes.
        """
        # Check if current user has permission to create users
        current_user = await self.get_current_user()
        if (
            current_user is None
            or UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            raise PermissionError("Only super admins can create users")

        # Check if requested scopes are valid
        if UserScope.SUPER_ADMIN in request.user_scopes:
            # Only super admins can create other super admins
            if (
                current_user is None
                or UserScope.SUPER_ADMIN not in current_user.user_scopes
            ):
                raise PermissionError("Only super admins can create super admin users")

        # Create the user info with generated ID and timestamps
        from uuid import uuid4

        user_info = UserInfo(
            id=base62.encodebytes(uuid4().bytes),
            name=request.name,
            avatar_url=request.avatar_url,
            language=request.language,
            default_llm_model=request.default_llm_model,
            email=request.email,
            accepted_tos=request.accepted_tos,
            user_scopes=request.user_scopes,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        # Add to session and commit
        self.session.add(user_info)
        await self.session.commit()
        await self.session.refresh(user_info)

        return user_info

    async def update_user(self, request: UpdateUserRequest) -> UserInfo:
        """
        Update a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to update users or grant the requested
        scopes.
        """
        # Check if user exists
        existing_user = await self._get_user_by_id_direct(request.id)
        if existing_user is None:
            raise ValueError(f"User with id {request.id} not found")

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

        # Check scope permissions
        if UserScope.SUPER_ADMIN in request.user_scopes:
            # Only super admins can grant super admin privileges
            if UserScope.SUPER_ADMIN not in current_user.user_scopes:
                raise PermissionError(
                    "Only super admins can grant super admin privileges"
                )

        # Update the user
        for name in UpdateUserRequest.model_fields:
            new_value = getattr(request, name)
            if new_value is not None:
                setattr(existing_user, name, new_value)
        existing_user.updated_at = utc_now()

        await self.session.commit()
        await self.session.refresh(existing_user)

        return existing_user

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to delete users.
        """
        # Check if current user has permission to delete users
        current_user = await self.get_current_user()
        if (
            current_user is None
            or UserScope.SUPER_ADMIN not in current_user.user_scopes
        ):
            raise PermissionError("Only super admins can delete users")

        # Check if user exists
        existing_user = await self._get_user_by_id_direct(user_id)
        if existing_user is None:
            return False

        # Delete the user
        await self.session.delete(existing_user)
        await self.session.commit()

        return True

    async def _get_current_user_without_recursion(self) -> UserInfo | None:
        """Get current user without causing recursion in permission checks."""
        if self.current_user_id is None:
            return None

        query = select(UserInfo).where(UserInfo.id == self.current_user_id)
        result = await self.session.execute(query)
        stored_user = result.scalar_one_or_none()
        return stored_user

    async def _get_user_by_id_direct(self, user_id: str) -> UserInfo | None:
        """Get user by ID directly without permission checks."""
        query = select(UserInfo).where(UserInfo.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class SQLUserServiceResolver(UserServiceResolver):
    current_user_id: str | None = None

    def get_unsecured_resolver(self) -> Callable:
        return self.resolve

    def get_resolver_for_user(self) -> Callable:
        logger.warning(
            "Using unsecured user service resolver - returning unsecured resolver"
        )
        return self.resolve

    def resolve(
        self, session: AsyncSession = Depends(async_session_dependency)
    ) -> UserService:
        return SQLUserService(session, self.current_user_id)
