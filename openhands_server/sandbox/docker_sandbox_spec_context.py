from dataclasses import dataclass, field
from datetime import datetime

import docker
from docker.errors import APIError, NotFound

from openhands_server.sandbox.sandbox_spec_context import SandboxSpecContext
from openhands_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)
from openhands_server.utils.date_utils import utc_now


@dataclass
class DockerSandboxSpecContext(SandboxSpecContext):
    """
    Sandbox spec context for docker images. By default, all images with the repository given
    are loaded and returned (They may have different tag) The combination of the repository
    and tag is treated as the id in the resulting image.
    """  # noqa: E501

    client: docker.DockerClient = field(default=None)
    repository: str = "ghcr.io/all-hands-ai/runtime"
    command: str = "python -u -m openhands_server.runtime"
    initial_env: dict[str, str] = field(default_factory=dict)
    working_dir: str = "/openhands/code"

    def _docker_image_to_sandbox_specs(self, image) -> SandboxSpecInfo:
        """Convert a Docker image to SandboxSpecInfo"""
        # Extract repository and tag from image tags
        # Use the first tag if multiple tags exist, or use the image ID if no tags
        if image.tags:
            image_id = image.tags[0]  # Use repository:tag as ID
        else:
            image_id = image.id[:12]  # Use short image ID if no tags

        # Parse creation time from image attributes
        created_str = image.attrs.get("Created", "")
        try:
            # Docker timestamps are in ISO format
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = utc_now()

        return SandboxSpecInfo(
            id=image_id,
            command=self.command,
            created_at=created_at,
            initial_env=self.initial_env,
            working_dir=self.working_dir,
        )

    async def search_sandbox_specs(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxSpecInfoPage:
        """Search for runtime images"""
        try:
            # Get all images that match the repository
            images = self.client.images.list(name=self.repository)

            # Convert Docker images to SandboxSpecInfo
            sandbox_specs = []
            for image in images:
                # Only include images that have tags matching our repository
                if image.tags:
                    for tag in image.tags:
                        if tag.startswith(self.repository):
                            sandbox_specs.append(
                                self._docker_image_to_sandbox_specs(image)
                            )
                            break  # Only add once per image, even if multiple matching tags  # noqa: E501

            # Apply pagination
            start_idx = 0
            if page_id:
                try:
                    start_idx = int(page_id)
                except ValueError:
                    start_idx = 0

            end_idx = start_idx + limit
            paginated_images = sandbox_specs[start_idx:end_idx]

            # Determine next page ID
            next_page_id = None
            if end_idx < len(sandbox_specs):
                next_page_id = str(end_idx)

            return SandboxSpecInfoPage(
                items=paginated_images, next_page_id=next_page_id
            )

        except APIError:
            # Return empty page if there's an API error
            return SandboxSpecInfoPage(items=[], next_page_id=None)

    async def get_sandbox_spec(self, id: str) -> SandboxSpecInfo | None:
        """Get a single runtime image info by ID"""
        try:
            # Try to get the image by ID (which should be repository:tag)
            image = self.client.images.get(id)
            return self._docker_image_to_sandbox_specs(image)
        except (NotFound, APIError):
            return None



    async def __aenter__(self):
        """Start using this sandbox spec context"""
        if self.client is None:
            self.client = docker.from_env()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop using this sandbox spec context"""
        # Docker client doesn't need explicit cleanup
        pass

    @classmethod
    async def get_instance(cls, *args, **kwargs) -> "DockerSandboxSpecContext":
        """Get an instance of sandbox spec context. Parameters are not specified
        so that they can be defined in the implementation classes and overridden using
        FastAPI's dependency injection. This allows merging global config with
        user / request specific variables."""
        return cls(*args, **kwargs)
