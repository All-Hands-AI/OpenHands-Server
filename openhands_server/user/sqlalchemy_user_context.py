"""SQLAlchemy implementation of UserContext.

This implementation provides CRUD operations for users with the following features:
- Permission-based access control (regular users can only see/modify themselves)
- Super admin users can manage all users and create other users
- Proper validation of user scopes and permissions
- Pagination support for user search
- Full async/await support using SQLAlchemy async sessions

Key components:
- SQLAlchemyUserContext: Main context class implementing all CRUD operations
- SQLAlchemyUserContextResolver: Dependency injection resolver for FastAPI
- StoredUser: Database model with proper Pydantic conversion methods
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.database import async_session_dependency
from openhands_server.user.user_context import UserContext
from openhands_server.user.user_db_models import StoredUser
from openhands_server.user.user_models import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserInfoPage,
    UserScope,
)
from openhands_server.utils.date_utils import utc_now


class SQLAlchemyUserContext(UserContext):
    """SQLAlchemy implementation of UserContext."""

    def __init__(self, session: AsyncSession, current_user_id: str | None = None):
        """
        Initialize the SQLAlchemy user context.

        Args:
            session: The async SQLAlchemy session
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
        if current_user is None or UserScope.SUPER_ADMIN not in current_user.user_scopes:
            # Regular users can only see themselves
            if self.current_user_id is None:
                return UserInfoPage(items=[], next_page_id=None)
            
            user = await self.get_user(self.current_user_id)
            if user is None:
                return UserInfoPage(items=[], next_page_id=None)
            
            return UserInfoPage(items=[user], next_page_id=None)

        # Super admin can search all users
        query = select(StoredUser)

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
        query = query.limit(limit + 1).order_by(StoredUser.created_at.desc())

        result = await self.session.execute(query)
        stored_users = result.scalars().all()

        # Check if there are more results
        has_more = len(stored_users) > limit
        if has_more:
            stored_users = stored_users[:limit]

        # Convert to Pydantic models
        items = [user.to_pydantic() for user in stored_users]

        # Calculate next page ID
        next_page_id = None
        if has_more:
            next_page_id = str(offset + limit)

        return UserInfoPage(items=items, next_page_id=next_page_id)

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

        query = select(StoredUser).where(StoredUser.id == id)
        result = await self.session.execute(query)
        stored_user = result.scalar_one_or_none()

        if stored_user is None:
            return None

        return stored_user.to_pydantic()

    async def create_user(self, request: CreateUserRequest) -> UserInfo:
        """
        Create a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to create users or grant the requested
        scopes.
        """
        # Check if current user has permission to create users
        current_user = await self.get_current_user()
        if current_user is None or UserScope.SUPER_ADMIN not in current_user.user_scopes:
            raise PermissionError("Only super admins can create users")

        # Check if requested scopes are valid
        if UserScope.SUPER_ADMIN in request.user_scopes:
            # Only super admins can create other super admins
            if current_user is None or UserScope.SUPER_ADMIN not in current_user.user_scopes:
                raise PermissionError("Only super admins can create super admin users")

        # Create the user info with generated ID and timestamps
        from uuid import uuid4
        
        user_info = UserInfo(
            id=uuid4().hex,
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

        # Convert to database model
        stored_user = StoredUser.from_pydantic(user_info)

        # Add to session and commit
        self.session.add(stored_user)
        await self.session.commit()
        await self.session.refresh(stored_user)

        # Return the Pydantic model
        return stored_user.to_pydantic()

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
                raise PermissionError("Only super admins can grant super admin privileges")

        # Update the user
        existing_user.name = request.name
        existing_user.avatar_url = request.avatar_url
        existing_user.language = request.language
        existing_user.default_llm_model = request.default_llm_model
        existing_user.email = request.email
        existing_user.accepted_tos = request.accepted_tos
        existing_user.user_scopes = request.user_scopes
        existing_user.updated_at = utc_now()

        await self.session.commit()
        await self.session.refresh(existing_user)

        return existing_user.to_pydantic()

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete a user if possible. Raise a PermissionError if it is not - the
        current user may not have permission to delete users.
        """
        # Check if current user has permission to delete users
        current_user = await self.get_current_user()
        if current_user is None or UserScope.SUPER_ADMIN not in current_user.user_scopes:
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

        query = select(StoredUser).where(StoredUser.id == self.current_user_id)
        result = await self.session.execute(query)
        stored_user = result.scalar_one_or_none()

        if stored_user is None:
            return None

        return stored_user.to_pydantic()

    async def _get_user_by_id_direct(self, user_id: str) -> StoredUser | None:
        """Get user by ID directly without permission checks."""
        query = select(StoredUser).where(StoredUser.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class SQLAlchemyUserContextResolver:
    """Resolver for SQLAlchemy-based user context."""

    def __init__(self, current_user_id: str | None = None):
        """
        Initialize the resolver with the current user ID.

        Args:
            current_user_id: The ID of the current user
        """
        self.current_user_id = current_user_id

    def get_resolver(self) -> Callable:
        return self.resolve

    def resolve(
        self, session: AsyncSession = Depends(async_session_dependency)
    ) -> UserContext:
        return SQLAlchemyUserContext(session, self.current_user_id)