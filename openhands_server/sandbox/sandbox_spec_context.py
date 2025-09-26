import asyncio
from abc import ABC, abstractmethod
from typing import Callable

from openhands.sdk.utils.models import DiscriminatedUnionMixin
from openhands_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)


class SandboxSpecContext(ABC):
    """
    Sandbox specs available to the current user. At present this is read only. The
    plan is that later this class will allow building and deleting sandbox specs and
    limiting access of images by user and group. It would also be nice to be able to
    set the desired number of warm sandboxes for a spec and scale this up and down.
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
        self, sandbox_spec_ids: list[str]
    ) -> list[SandboxSpecInfo | None]:
        """Get a batch of sandbox specs, returning None for any spec which was not
        found"""
        results = await asyncio.gather(
            *[
                self.get_sandbox_spec(sandbox_spec_id)
                for sandbox_spec_id in sandbox_spec_ids
            ]
        )
        return results

    # Lifecycle methods

    async def __aenter__(self):
        """Start using this sandbox spec context"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox spec context"""


class SandboxSpecContextResolver(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    def get_resolver(self) -> Callable:
        """
        Get a resolver which may be used to resolve an instance of sandbox spec context.
        """
