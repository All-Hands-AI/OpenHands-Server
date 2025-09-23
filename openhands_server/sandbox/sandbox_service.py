from abc import ABC, abstractmethod
from uuid import UUID

from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage
from openhands_server.user.user_context import UserContext
from openhands_server.utils.import_utils import get_impl


class SandboxService(ABC):
    """
    Service for accessing sandboxes in which conversations may be run.
    """

    @abstractmethod
    async def search_sandboxes(
        self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100
    ) -> SandboxPage:
        """Search for sandboxes"""

    @abstractmethod
    async def get_sandbox(self, id: UUID) -> SandboxInfo | None:
        """Get a single sandbox. Return None if the sandbox was not found."""

    @abstractmethod
    async def batch_get_sandboxes(self, ids: list[UUID]) -> list[SandboxInfo | None]:
        """Get a batch of sandboxes, returning None for any which were not found."""
        results = []
        for id in ids:
            result = await self.get_sandbox(id)
            results.append(result)
        return results

    @abstractmethod
    async def start_sandbox(
        self, user_context: UserContext, sandbox_spec_id: str
    ) -> SandboxInfo:
        """Begin the process of starting a sandbox. Return the info on the new sandbox"""

    @abstractmethod
    async def resume_sandbox(self, id: UUID) -> bool:
        """Begin the process of resuming a sandbox. Return True if the sandbox exists and is being resumed or is already running. Return False if the sandbox did not exist"""

    @abstractmethod
    async def pause_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox. Return True if the sandbox exists and is being paused or is already paused. Return False if the sandbox did not exist"""

    @abstractmethod
    async def delete_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox (self, Which may involve stopping it first). Return False if the sandbox did not exist"""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox service"""

    @classmethod
    @abstractmethod
    def get_instance(cls) -> "SandboxService":
        """Get an instance of sandbox service"""


_sandbox_service = None


def get_default_sandbox_service():
    global _sandbox_service
    if _sandbox_service:
        return _sandbox_service
    _sandbox_service = get_impl(
        SandboxService,
        "openhands_server.sandbox.docker_sandbox_service.DockerSandboxService",
    )()
    return _sandbox_service
