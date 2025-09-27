import os
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from uuid import UUID, uuid4

import base62
import docker
from docker.errors import APIError, NotFound
from fastapi import Depends

from openhands_server.dependency import get_dependency_resolver
from openhands_server.sandbox.docker_sandbox_spec_context import get_docker_client
from openhands_server.sandbox.sandbox_context import (
    SandboxContext,
    SandboxContextResolver,
)
from openhands_server.sandbox.sandbox_errors import SandboxError
from openhands_server.sandbox.sandbox_models import (
    SandboxInfo,
    SandboxPage,
    SandboxStatus,
)
from openhands_server.sandbox.sandbox_spec_context import SandboxSpecContext
from openhands_server.utils.date_utils import utc_now


SESSION_API_KEY_VARIABLE = "OH_SESSION_API_KEYS_0"


@dataclass
class VolumeMount:
    host_path: str
    container_path: str
    mode: str = "rw"


@dataclass
class ExposedPort:
    """Exposed port. A free port will be found for this and an environment variable
    set"""

    name: str
    description: str
    container_port: int = 8000


@dataclass
class DockerSandboxContext(SandboxContext):
    sandbox_spec_context: SandboxSpecContext
    container_name_prefix: str = "openhands-agent-server-"
    exposed_url_pattern: str = "http://localhost:{port}"
    docker_client: docker.DockerClient = field(default_factory=get_docker_client)
    mounts: list[VolumeMount] = field(default_factory=list)
    exposed_port: list[ExposedPort] = field(
        default_factory=lambda: [
            ExposedPort(
                "APPLICATION_SERVER_PORT",
                "The port on which the application server runs within the container",
            )
        ]
    )

    def _find_unused_port(self) -> int:
        """Find an unused port on the host machine"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _container_name_from_id(self, container_id: UUID) -> str:
        """Generate container name from UUID"""
        return f"{self.container_name_prefix}{base62.encodebytes(container_id.bytes)}"

    def _sandbox_id_from_container_name(self, container_name: str) -> UUID | None:
        """Extract runtime ID from container name"""
        if not container_name.startswith(self.container_name_prefix):
            return None

        uuid_str = container_name[len(self.container_name_prefix) :]
        try:
            return UUID(int=base62.decode(uuid_str))
        except ValueError:
            return None

    def _docker_status_to_sandbox_status(self, docker_status: str) -> SandboxStatus:
        """Convert Docker container status to SandboxStatus"""
        status_mapping = {
            "running": SandboxStatus.RUNNING,
            "paused": SandboxStatus.PAUSED,
            "exited": SandboxStatus.DELETED,
            "created": SandboxStatus.STARTING,
            "restarting": SandboxStatus.STARTING,
            "removing": SandboxStatus.DELETED,
            "dead": SandboxStatus.ERROR,
        }
        return status_mapping.get(docker_status.lower(), SandboxStatus.ERROR)

    def _get_container_env_vars(self, container) -> dict[str, str | None]:
        env_vars_list = container.attrs["Config"]["Env"]
        result = {}
        for env_var in env_vars_list:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                result[key] = value
            else:
                # Handle cases where an environment variable might not have a value
                result[env_var] = None
        return result

    def _container_to_sandbox_info(self, container) -> SandboxInfo | None:
        """Convert Docker container to SandboxInfo"""
        # Extract sandbox ID from container name
        sandbox_id = self._sandbox_id_from_container_name(container.name)
        if sandbox_id is None:
            return None

        # Get user_id and sandbox_spec_id from labels
        labels = container.labels or {}
        created_by_user_id = labels.get("created_by_user_id")
        sandbox_spec_id = labels.get("sandbox_spec_id")

        if not created_by_user_id or not sandbox_spec_id:
            return None

        # Convert Docker status to runtime status
        status = self._docker_status_to_sandbox_status(container.status)

        # Parse creation time
        created_str = container.attrs.get("Created", "")
        try:
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = utc_now()

        # Get URL and session key for running containers
        url = None
        session_api_key = None

        if status == SandboxStatus.RUNNING:
            # Get the first exposed port mapping
            port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            if port_bindings:
                for container_port, host_bindings in port_bindings.items():
                    if host_bindings:
                        host_port = host_bindings[0]["HostPort"]
                        url = self.exposed_url_pattern.format(port=host_port)
                        break

            # Get session API key
            env = self._get_container_env_vars(container)
            session_api_key = env[SESSION_API_KEY_VARIABLE]

        return SandboxInfo(
            id=sandbox_id,
            created_by_user_id=created_by_user_id,
            sandbox_spec_id=sandbox_spec_id,
            status=status,
            url=url,
            session_api_key=session_api_key,
            created_at=created_at,
        )

    async def search_sandboxes(
        self,
        created_by_user_id__eq: str | None = None,
        page_id: str | None = None,
        limit: int = 100,
    ) -> SandboxPage:
        """Search for sandboxes"""
        try:
            # Get all containers with our prefix
            all_containers = self.docker_client.containers.list(all=True)
            sandboxes = []

            for container in all_containers:
                if container.name.startswith(self.container_name_prefix):
                    sandbox_info = self._container_to_sandbox_info(container)
                    if sandbox_info:
                        # Filter by user_id if specified
                        if (
                            created_by_user_id__eq is None
                            or sandbox_info.created_by_user_id == created_by_user_id__eq
                        ):
                            sandboxes.append(sandbox_info)

            # Sort by creation time (newest first)
            sandboxes.sort(key=lambda x: x.created_at, reverse=True)

            # Apply pagination
            start_idx = 0
            if page_id:
                try:
                    start_idx = int(page_id)
                except ValueError:
                    start_idx = 0

            end_idx = start_idx + limit
            paginated_containers = sandboxes[start_idx:end_idx]

            # Determine next page ID
            next_page_id = None
            if end_idx < len(sandboxes):
                next_page_id = str(end_idx)

            return SandboxPage(items=paginated_containers, next_page_id=next_page_id)

        except APIError:
            return SandboxPage(items=[], next_page_id=None)

    async def get_sandbox(self, id: UUID) -> SandboxInfo | None:
        """Get a single sandbox info"""
        try:
            container_name = self._container_name_from_id(id)
            container = self.docker_client.containers.get(container_name)
            return self._container_to_sandbox_info(container)
        except (NotFound, APIError):
            return None

    async def start_sandbox(self, sandbox_spec_id: str | None = None) -> SandboxInfo:
        """Start a new sandbox"""
        if sandbox_spec_id is None:
            sandbox_spec = await self.sandbox_spec_context.get_default_sandbox_spec()
        else:
            sandbox_spec = await self.sandbox_spec_context.get_sandbox_spec(
                sandbox_spec_id
            )

        if sandbox_spec is None:
            raise ValueError("Sandbox Spec not found")

        # Generate container ID and name
        container_id = uuid4()
        container_name = self._container_name_from_id(container_id)

        # Prepare environment variables
        env_vars = sandbox_spec.initial_env.copy()

        session_api_key = base62.encodebytes(os.urandom(32))
        env_vars[SESSION_API_KEY_VARIABLE] = session_api_key
        # env_vars[WEBHOOK_CALLBACK_VARIABLE] =

        # Prepare port mappings and add port environment variables
        port_mappings = {}
        for exposed_port in self.exposed_port:
            host_port = self._find_unused_port()
            port_mappings[exposed_port.container_port] = host_port
            # Add port as environment variable
            env_vars[exposed_port.name] = str(host_port)

        # Prepare labels
        labels = {
            "created_by_user_id": "NO_USER",  # TODO: Integrate auth service
            "sandbox_spec_id": sandbox_spec.id,
        }

        # TODO: Handle mounts - for now, we'll create a basic volume mount
        volumes = {
            f"openhands-workspace-{container_id}": {
                "bind": sandbox_spec.working_dir,
                "mode": "rw",
            }
        }

        try:
            # Create and start the container
            container = self.docker_client.containers.run(
                image=sandbox_spec.id,
                # command=sandbox_spec.command,  # TODO: Re-enable this later
                name=container_name,
                environment=env_vars,  # TODO: Re-enable this later
                ports=port_mappings,
                volumes=volumes,
                working_dir=sandbox_spec.working_dir,
                labels=labels,
                detach=True,
                remove=False,
            )

            sandbox_info = self._container_to_sandbox_info(container)
            assert sandbox_info is not None
            return sandbox_info

        except APIError as e:
            raise SandboxError(f"Failed to start container: {e}")

    async def resume_sandbox(self, id: UUID) -> bool:
        """Resume a paused sandbox"""
        try:
            container_name = self._container_name_from_id(id)
            container = self.docker_client.containers.get(container_name)

            if container.status == "paused":
                container.unpause()
            elif container.status == "exited":
                container.start()

            return True
        except (NotFound, APIError):
            return False

    async def pause_sandbox(self, id: UUID) -> bool:
        """Pause a running sandbox"""
        try:
            container_name = self._container_name_from_id(id)
            container = self.docker_client.containers.get(container_name)

            if container.status == "running":
                container.pause()

            return True
        except (NotFound, APIError):
            return False

    async def delete_sandbox(self, id: UUID) -> bool:
        """Delete a sandbox"""
        try:
            container_name = self._container_name_from_id(id)
            container = self.docker_client.containers.get(container_name)

            # Stop the container if it's running
            if container.status in ["running", "paused"]:
                container.stop(timeout=10)

            # Remove the container
            container.remove()

            # Remove associated volume
            try:
                volume_name = f"openhands-workspace-{id}"
                volume = self.docker_client.volumes.get(volume_name)
                volume.remove()
            except (NotFound, APIError):
                # Volume might not exist or already removed
                pass

            return True
        except (NotFound, APIError):
            return False


class DockerSandboxContextResolver(SandboxContextResolver):
    def get_resolver(self) -> Callable:
        sandbox_spec_resolver = get_dependency_resolver().sandbox_spec.get_resolver()

        # Define inline to prevent circular lookup
        def resolve(
            sandbox_spec_context: SandboxSpecContext = Depends(sandbox_spec_resolver),
        ) -> SandboxContext:
            return DockerSandboxContext(sandbox_spec_context=sandbox_spec_context)

        return resolve
