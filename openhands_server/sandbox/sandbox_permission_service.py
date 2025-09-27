import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.sandbox.sandbox_permission_models import (
    SandboxPermission,
    SandboxPermissionPage,
)


_logger = logging.getLogger(__name__)


class SandboxPermissionService(ABC):
    """
    Service for accessing sandbox permissions available to the current user.
    """

    @abstractmethod
    async def search_sandbox_permissions(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxPermissionPage:
        """Search for sandboxes"""

    @abstractmethod
    async def get_sandbox_permission(self, id: UUID) -> SandboxPermission | None:
        """Get a single sandbox. Return None if the sandbox was not found."""

    @abstractmethod
    async def add_sandbox_permission(
        self, sandbox_id: str, user_id: str, full_access: bool = False
    ) -> SandboxPermission:
        """Add a sandbox permission for the user given to the sandbox given. Raise a
        PermissionError if the current user does not have full access to the sandbox"""

    @abstractmethod
    async def delete_sandbox_permission(self, sandbox_permission_id: UUID) -> bool:
        """Delete a sandbox permission. Return false if the permission did not exist,
        the current user did not have full access to the sandbox, or permission
        belonged to the current user (User's can't revoke their own permissions)."""

    @abstractmethod
    async def batch_get_sandbox_permissions(
        self, sandbox_permission_ids: list[UUID]
    ) -> list[SandboxPermission | None]:
        """Get a batch of sandboxes, returning None for any which were not found."""
        results = await asyncio.gather(
            *[
                self.get_sandbox_permission(sandbox_permission_id)
                for sandbox_permission_id in sandbox_permission_ids
            ]
        )
        return results


class SandboxPermissionServiceResolver(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def get_unsecured_resolver(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of sandbox
        permission service.
        """

    @abstractmethod
    def get_resolver_for_user(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of sandbox
        permission service limited to the current user.
        """
