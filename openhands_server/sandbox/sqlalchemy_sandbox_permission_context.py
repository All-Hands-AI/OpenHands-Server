"""SQLAlchemy implementation of SandboxPermissionContext."""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from openhands_server.database import async_session_dependency
from openhands_server.sandbox.sandbox_permission_context import (
    SandboxPermissionContext,
)
from openhands_server.sandbox.sandbox_permission_db_models import (
    StoredSandboxPermission,
)
from openhands_server.sandbox.sandbox_permission_models import (
    SandboxPermission,
    SandboxPermissionPage,
)


class SQLAlchemySandboxPermissionContext(SandboxPermissionContext):
    """SQLAlchemy implementation of SandboxPermissionContext."""

    def __init__(self, session: AsyncSession, current_user_id: str | None = None):
        """
        Initialize the SQLAlchemy sandbox permission context.

        Args:
            session: The async SQLAlchemy session
            current_user_id: The ID of the current user (for permission checks)
        """
        self.session = session
        self.current_user_id = current_user_id

    async def search_sandbox_permissions(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxPermissionPage:
        """Search for sandbox permissions available to the current user."""
        # Build the base query - only show permissions for the current user
        conditions = []
        if self.current_user_id is not None:
            conditions.append(StoredSandboxPermission.user_id == self.current_user_id)

        stmt = select(StoredSandboxPermission)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Handle pagination
        if page_id is not None:
            try:
                offset = int(page_id)
                stmt = stmt.offset(offset)
            except ValueError:
                # If page_id is not a valid integer, start from beginning
                offset = 0
        else:
            offset = 0

        # Apply limit and get one extra to check if there are more results
        stmt = stmt.limit(limit + 1).order_by(StoredSandboxPermission.timestamp.desc())

        result = await self.session.execute(stmt)
        stored_permissions = result.scalars().all()

        # Check if there are more results
        has_more = len(stored_permissions) > limit
        if has_more:
            stored_permissions = stored_permissions[:limit]

        # Convert to Pydantic models
        items = [permission.to_pydantic() for permission in stored_permissions]

        # Calculate next page ID
        next_page_id = None
        if has_more:
            next_page_id = str(offset + limit)

        return SandboxPermissionPage(items=items, next_page_id=next_page_id)

    async def get_sandbox_permission(self, id: UUID) -> SandboxPermission | None:
        """Get a single sandbox permission, returning None if not found or not
        accessible."""
        conditions = [StoredSandboxPermission.id == id]

        # Only allow access to permissions for the current user
        if self.current_user_id is not None:
            conditions.append(StoredSandboxPermission.user_id == self.current_user_id)

        stmt = select(StoredSandboxPermission).where(and_(*conditions))
        result = await self.session.execute(stmt)
        stored_permission = result.scalar_one_or_none()

        if stored_permission is None:
            return None

        return stored_permission.to_pydantic()

    async def add_sandbox_permission(
        self, sandbox_id: str, user_id: str, full_access: bool = False
    ) -> SandboxPermission:
        """
        Add a sandbox permission for the user given to the sandbox given.

        Raises PermissionError if the current user does not have full access to
        the sandbox.
        """
        # Check if current user has full access to this sandbox
        if self.current_user_id is not None:
            current_user_permission_stmt = select(StoredSandboxPermission).where(
                and_(
                    StoredSandboxPermission.sandbox_id == sandbox_id,
                    StoredSandboxPermission.user_id == self.current_user_id,
                    StoredSandboxPermission.full_access == True,  # noqa: E712
                )
            )
            result = await self.session.execute(current_user_permission_stmt)
            current_user_permission = result.scalar_one_or_none()

            if current_user_permission is None:
                raise PermissionError(
                    "Current user does not have full access to this sandbox"
                )

        # Create the new permission
        sandbox_permission = SandboxPermission(
            sandbox_id=sandbox_id,
            user_id=user_id,
            created_by_user_id=self.current_user_id,
            full_access=full_access,
        )

        # Convert to database model
        stored_permission = StoredSandboxPermission.from_pydantic(sandbox_permission)

        # Add to session and commit
        self.session.add(stored_permission)
        await self.session.commit()
        await self.session.refresh(stored_permission)

        # Return the Pydantic model
        return stored_permission.to_pydantic()

    async def delete_sandbox_permission(self, sandbox_permission_id: UUID) -> bool:
        """
        Delete a sandbox permission.

        Returns False if:
        - The permission did not exist
        - The current user did not have full access to the sandbox
        - The permission belonged to the current user (users can't revoke their own
          permissions)
        """
        # Get the permission to delete
        stmt = select(StoredSandboxPermission).where(
            StoredSandboxPermission.id == sandbox_permission_id
        )
        result = await self.session.execute(stmt)
        permission_to_delete = result.scalar_one_or_none()

        if permission_to_delete is None:
            return False

        # Check if the permission belongs to the current user (not allowed to delete
        # own permission)
        if (
            self.current_user_id is not None
            and permission_to_delete.user_id == self.current_user_id  # type: ignore
        ):
            return False

        # Check if current user has full access to this sandbox
        if self.current_user_id is not None:
            current_user_permission_stmt = select(StoredSandboxPermission).where(
                and_(
                    StoredSandboxPermission.sandbox_id
                    == permission_to_delete.sandbox_id,
                    StoredSandboxPermission.user_id == self.current_user_id,
                    StoredSandboxPermission.full_access == True,  # noqa: E712
                )
            )
            result = await self.session.execute(current_user_permission_stmt)
            current_user_permission = result.scalar_one_or_none()

            if current_user_permission is None:
                return False

        # Delete the permission
        await self.session.delete(permission_to_delete)
        await self.session.commit()
        return True

    async def batch_get_sandbox_permissions(
        self, sandbox_permission_ids: list[UUID]
    ) -> list[SandboxPermission | None]:
        """Get a batch of sandbox permissions, returning None for any which were
        not found."""
        if not sandbox_permission_ids:
            return []

        conditions = [StoredSandboxPermission.id.in_(sandbox_permission_ids)]

        # Only allow access to permissions for the current user
        if self.current_user_id is not None:
            conditions.append(
                StoredSandboxPermission.user_id == self.current_user_id  # type: ignore
            )

        stmt = select(StoredSandboxPermission).where(and_(*conditions))
        result = await self.session.execute(stmt)
        stored_permissions = result.scalars().all()

        # Create a mapping of ID to permission
        permission_map = {perm.id: perm.to_pydantic() for perm in stored_permissions}

        # Return results in the same order as requested, with None for
        # missing permissions
        return [
            permission_map.get(perm_id)  # type: ignore
            for perm_id in sandbox_permission_ids
        ]


class SQLAlchemySandboxPermissionContextResolver:
    """Resolver for SQLAlchemy-based sandbox permission context."""

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
    ) -> SandboxPermissionContext:
        return SQLAlchemySandboxPermissionContext(session, self.current_user_id)
