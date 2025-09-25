import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from uuid import UUID

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.sandbox.sandbox_models import SandboxInfo, SandboxPage


class SandboxContext(ABC):
    """
    Context for accessing sandboxes available to the current user in which
    conversations may be run.
    """

    @abstractmethod
    async def search_sandboxes(
        self,
        created_by_user_id__eq: str | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        """Search for sandboxes"""

    @abstractmethod
    async def get_sandbox(self, id: UUID) -> SandboxInfo | None:
        """Get a single sandbox. Return None if the sandbox was not found."""

    async def batch_get_sandboxes(
        self, sandbox_ids: list[UUID]
    ) -> list[SandboxInfo | None]:
        """Get a batch of sandboxes, returning None for any which were not found."""
        results = await asyncio.gather(
            *[self.get_sandbox(sandbox_id) for sandbox_id in sandbox_ids]
        )
        return results

    @abstractmethod
    async def start_sandbox(self, sandbox_spec_id: str) -> SandboxInfo:
        """Begin the process of starting a sandbox. Return the info on the new
        sandbox"""

    @abstractmethod
    async def resume_sandbox(self, id: UUID) -> bool:
        """Begin the process of resuming a sandbox. Return True if the sandbox exists
        and is being resumed or is already running. Return False if the sandbox did
        not exist"""

    @abstractmethod
    async def pause_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox. Return True if the sandbox exists
        and is being paused or is already paused. Return False if the sandbox did
        not exist"""

    @abstractmethod
    async def delete_sandbox(self, id: UUID) -> bool:
        """Begin the process of deleting a sandbox (self, Which may involve stopping
        it first). Return False if the sandbox did not exist"""

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox context"""


class SandboxContextFactory(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def with_instance(
        self, *args, **kwargs
    ) -> AsyncGenerator["SandboxContext", None]:
        """
        Get an instance of sandbox context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables.
        """
        yield SandboxContext()  # type: ignore
