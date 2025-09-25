import asyncio
from abc import ABC, abstractmethod
from typing import Type
from uuid import UUID

from openhands_server.config import get_global_config
from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage
from openhands_server.utils.import_utils import get_impl


class SandboxContext(ABC):
    """
    Context for accessing sandboxes available to the current user in which conversations may be run.
    """  # noqa: E501

    @abstractmethod
    async def search_sandboxes(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxPage:
        """Search for sandboxes"""

    @abstractmethod
    async def get_sandbox(self, id: UUID) -> SandboxInfo | None:
        """Get a single sandbox. Return None if the sandbox was not found."""

    async def batch_get_sandboxes(self, ids: list[UUID]) -> list[SandboxInfo | None]:
        """Get a batch of sandboxes, returning None for any which were not found."""
        return await asyncio.gather(*[self.get_sandbox(id) for id in ids])

    @abstractmethod
    async def start_sandbox(self, sandbox_spec_id: str) -> SandboxInfo:
        """Begin the process of starting a sandbox. Return the info on the new sandbox"""  # noqa: E501

    @abstractmethod
    async def resume_sandbox(self, id: UUID) -> bool:
        """Begin the process of resuming a sandbox. Return True if the sandbox exists and is being resumed or is already running. Return False if the sandbox did not exist"""  # noqa: E501

    @abstractmethod
    async def pause_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox. Return True if the sandbox exists and is being paused or is already paused. Return False if the sandbox did not exist"""  # noqa: E501

    @abstractmethod
    async def delete_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox (self, Which may involve stopping it first). Return False if the sandbox did not exist"""  # noqa: E501

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox context"""

    @classmethod
    @abstractmethod
    def get_instance(cls, *args, **kwargs) -> "SandboxContext":
        """Get an instance of sandbox context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables."""


_sandbox_context_type: Type[SandboxContext] | None = None


async def get_sandbox_context_type() -> Type[SandboxContext]:
    global _sandbox_context_type
    if _sandbox_context_type is None:
        config = get_global_config()
        _sandbox_context_type = get_impl(SandboxContext, config.sandbox_context_type)
    return await _sandbox_context_type


async def sandbox_context_dependency(*args, **kwargs):
    context_type = await get_sandbox_context_type()
    context = context_type.get_instance(*args, **kwargs)
    async with context:
        yield context


# Legacy compatibility function for existing code
async def get_default_sandbox_service():
    """Get default sandbox service - legacy compatibility function"""
    context_type = await get_sandbox_context_type()
    return context_type.get_instance()
