from abc import ABC, abstractmethod

from openhands_server.sandbox_spec.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)
from openhands_server.utils.import_utils import get_impl


class SandboxSpecService(ABC):
    """
    Service for accessing sandbox specs. At present this is read only. The plan is that later this class
    will allow building and deleting sandbox specs and limiting access of images by user and group.
    It would also be nice to be able to set the desired number of warm sandboxes for a spec and scale this
    up and down.
    """

    @abstractmethod
    async def search_sandbox_specs(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxSpecInfoPage:
        """Search for sandbox specs"""

    @abstractmethod
    async def get_sandbox_spec(self, id: str) -> SandboxSpecInfo | None:
        """Get a single sandbox spec, returning None if not found."""

    async def get_default_sandbox_spec(self) -> SandboxSpecInfo:
        """Get the default sandbox spec"""
        page = await self.search_sandbox_specs()
        return page.items[0]

    async def batch_get_sandbox_specs(
        self, ids: list[str]
    ) -> list[SandboxSpecInfo | None]:
        """Get a batch of sandbox specs, returning None for any spec which was not found"""
        results = [self.get_sandbox_spec(id) for id in ids]
        return results

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this runtime image service"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this runtime image service"""

    @classmethod
    @abstractmethod
    def get_instance(cls) -> "SandboxSpecService":
        """Get an instance of runtime image service"""


_sandbox_spec_service: SandboxSpecService = None


def get_default_sandbox_spec_service() -> SandboxSpecService:
    global _sandbox_spec_service
    if _sandbox_spec_service:
        return _sandbox_spec_service
    _sandbox_spec_service = get_impl(SandboxSpecService)
    return _sandbox_spec_service
