import asyncio
from abc import ABC, abstractmethod
from typing import Type

from openhands_server.config import get_global_config
from openhands_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)
from openhands_server.utils.import_utils import get_impl


class SandboxSpecContext(ABC):
    """
    Sandbox specs available to the current user. At present this is read only. The plan is that
    later this class will allow building and deleting sandbox specs and limiting access of images
    by user and group. It would also be nice to be able to set the desired number of warm
    sandboxes for a spec and scale this up and down.
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
        return await asyncio.gather(*[self.get_sandbox_spec(id) for id in ids])

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox spec context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox spec context"""

    @classmethod
    @abstractmethod
    async def get_instance(cls, *args, **kwargs) -> "SandboxSpecContext":
        """Get an instance of sandbox spec context"""


_sandbox_spec_context_type: Type[SandboxSpecContext] = None


async def get_sandbox_spec_context_type() -> Type[SandboxSpecContext]:
    global _sandbox_spec_context_type
    if _sandbox_spec_context_type is None:
        config = get_global_config()
        _sandbox_spec_context_type = get_impl(
            SandboxSpecContext, config.sandbox_spec_context_type
        )
    return _sandbox_spec_context_type


async def sandbox_spec_context_dependency(*args, **kwargs):
    context_type = await get_sandbox_spec_context_type()
    context = await context_type.get_instance(*args, **kwargs)
    async with context:
        yield context


# Legacy compatibility function for existing code
async def get_default_sandbox_spec_service():
    """Get default sandbox spec service - legacy compatibility function"""
    context_type = await get_sandbox_spec_context_type()
    return await context_type.get_instance()
