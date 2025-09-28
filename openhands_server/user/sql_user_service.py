# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
"""SQL implementation of UserService.

This implementation provides CRUD operations for users focused purely on SQL operations:
- Direct database access without permission checks
- Pagination support for user search
- Full async/await support using SQL async sessions

Security and permission checks are handled by ConstrainedUserService wrapper.

Key components:
- SQLUserService: Main service class implementing all CRUD operations
- SQLUserServiceResolver: Dependency injection resolver for FastAPI
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import base62
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.database import async_session_dependency
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
    UserSortOrder,
)
from openhands_server.user.user_service import UserService, UserServiceResolver
from openhands_server.utils.date_utils import utc_now


logger = logging.getLogger(__name__)


@dataclass
class SQLUserService(UserService):
    """SQL implementation of UserService focused on database operations."""

    session: AsyncSession

    async def get_current_user(self) -> UserInfo | None:
        """Get the current user."""
        return None

    async def search_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
        sort_order: UserSortOrder = UserSortOrder.EMAIL,
        page_id: str | None = None,
        limit: int = 100,
    ) -> UserInfoPage:
        """Search for users without permission checks."""
        query = select(UserInfo)

        # Apply filters
        conditions = []
        if name__contains is not None:
            conditions.append(UserInfo.name.like(name__contains))

        if email__contains is not None:
            conditions.append(UserInfo.email.like(email__contains))

        if user_scopes__contains is not None:
            conditions.append(UserInfo.user_scopes.contains(user_scopes__contains))

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
        query = query.limit(limit + 1)

        if sort_order:
            raise NotImplementedError()

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

    async def count_users(
        self,
        name__contains: str | None = None,
        email__contains: str | None = None,
        user_scopes__contains: UserScope | None = None,
    ) -> int:
        """Count users"""
        raise NotImplementedError()

    async def get_user(self, id: str) -> UserInfo | None:
        """Get a single user. Return None if the user was not found."""
        query = select(UserInfo).where(UserInfo.id == id)
        result = await self.session.execute(query)
        stored_user = result.scalar_one_or_none()
        return stored_user

    async def create_user(self, request: CreateUserRequest) -> UserInfo:
        """Create a user."""
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
        """Update a user."""
        # Check if user exists
        existing_user = await self.get_user(request.id)
        if existing_user is None:
            raise ValueError(f"User with id {request.id} not found")

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
        """Delete a user. Returns True if deleted, False if not found."""
        # Check if user exists
        existing_user = await self.get_user(user_id)
        if existing_user is None:
            return False

        # Delete the user
        await self.session.delete(existing_user)
        await self.session.commit()

        return True


class SQLUserServiceResolver(UserServiceResolver):
    def get_unsecured_resolver(self) -> Callable:
        return self._resolve_unsecured

    def get_resolver_for_user(self) -> Callable:
        return self._resolve_constrained

    def _resolve_unsecured(
        self, session: AsyncSession = Depends(async_session_dependency)
    ) -> UserService:
        """Resolve to SQLUserService without security wrapper."""
        return SQLUserService(session)

    def _resolve_constrained(
        self, session: AsyncSession = Depends(async_session_dependency)
    ) -> UserService:
        """Resolve to ConstrainedUserService wrapping SQLUserService."""
        service = SQLUserService(session)
        # TODO: Add auth and fix
        logger.warning("⚠️ Using Unsecured UserService!!!")
        # service = ConstrainedUserService(service, self.current_user_id)
        return service
