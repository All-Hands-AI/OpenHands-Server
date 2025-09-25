from abc import ABC, abstractmethod
from uuid import UUID

from openhands_server.sandbox.sandbox_permission_models import (
    SandboxPermission,
    SandboxPermissionPage,
)


class SandboxContext(ABC):
    """
    Context for accessing sandbox permissions available to the current user.
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
    async def batch_get_sandboxes(
        self, ids: list[UUID]
    ) -> list[SandboxPermission | None]:
        """Get a batch of sandboxes, returning None for any which were not found."""
        results = []
        for id in ids:
            result = await self.get_sandbox_permission(id)
            results.append(result)
        return results
