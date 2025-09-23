import secrets
import socket
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

import docker
from docker.errors import APIError, NotFound
from pydantic import SecretStr

from openhands_server.sandbox.sandbox_errors import SandboxError
from openhands_server.sandbox.sandbox_models import (
    SandboxInfo,
    SandboxPage,
    SandboxStatus,
)
from openhands_server.sandbox.sandbox_service import (
    SandboxService,
)
from openhands_server.sandbox_spec.docker_sandbox_spec_service import (
    DockerSandboxSpecService,
)
from openhands_server.sandbox_spec.sandbox_spec_service import (
    get_default_sandbox_spec_service,
)
from openhands_server.utils.date_utils import utc_now


@dataclass
class VolumeMount:
    host_path: str
    container_path: str
    mode: str = "rw"


@dataclass
class ExposedPort:
    """Exposed port. A free port will be found for this and an environment variable set"""

    name: str
    description: str


@dataclass
class DockerSandboxService(SandboxService):
    container_name_prefix: str = "openhands-runtime-"
    exposed_url_pattern: str = "http://localhost:{port}"
    sandbox_spec_service: DockerSandboxSpecService = field(
        default_factory=DockerSandboxSpecService.get_instance
    )
    mounts: list[VolumeMount] = field(default_factory=list)
    exposed_port: list[ExposedPort] = field(
        default_factory=lambda: [
            ExposedPort(
                "APPLICATION_SERVER_PORT",
                "The port on which the application server runs within the container",
            )
        ]
    )
    _client: docker.DockerClient | None = field(default=None)

    def _find_unused_port(self) -> int:
        """Find an unused port on the host machine"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _container_name_from_id(self, container_id: UUID) -> str:
        """Generate container name from UUID"""
        return f"{self.container_name_prefix}{container_id}"

    def _runtime_id_from_container_name(self, container_name: str) -> UUID | None:
        """Extract runtime ID from container name"""
        if not container_name.startswith(self.container_name_prefix):
            return None

        uuid_str = container_name[len(self.container_name_prefix) :]
        try:
            return UUID(uuid_str)
        except ValueError:
            return None

    def _docker_status_to_runtime_status(self, docker_status: str) -> SandboxStatus:
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

    def _container_to_runtime_info(self, container) -> SandboxInfo | None:
        """Convert Docker container to SandboxInfo"""
        # Extract runtime ID from container name
        runtime_id = self._runtime_id_from_container_name(container.name)
        if runtime_id is None:
            return None

        # Get user_id and sandbox_spec_id from labels
        labels = container.labels or {}
        user_id_str = labels.get("user_id")
        sandbox_spec_id = labels.get("sandbox_spec_id")

        if not user_id_str or not sandbox_spec_id:
            return None

        # Convert Docker status to runtime status
        status = self._docker_status_to_runtime_status(container.status)

        # Parse creation time
        created_str = container.attrs.get("Created", "")
        try:
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = utc_now()

        # Generate URL and session key for running containers
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

            # Generate session API key
            session_api_key = SecretStr(secrets.token_urlsafe(32))

        return SandboxInfo(
            id=runtime_id,
            user_id=user_id_str,
            sandbox_spec_id=sandbox_spec_id,
            status=status,
            url=url,
            session_api_key=session_api_key,
            created_at=created_at,
        )

    async def search_sandboxes(
        self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100
    ) -> SandboxPage:
        """Search for sandboxes"""
        try:
            # Get all containers with our prefix
            all_containers = self._client.containers.list(all=True)
            sandboxes = []

            for container in all_containers:
                if container.name.startswith(self.container_name_prefix):
                    runtime_info = self._container_to_runtime_info(container)
                    if runtime_info:
                        # Filter by user_id if specified
                        if user_id is None or runtime_info.user_id == str(user_id):
                            sandboxes.append(runtime_info)

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
            container = self._client.containers.get(container_name)
            return self._container_to_runtime_info(container)
        except (NotFound, APIError):
            return None

    async def batch_get_sandboxes(self, ids: list[UUID]) -> list[SandboxInfo | None]:
        """Get multiple sandbox infos"""
        results = []
        for sandbox_id in ids:
            sandbox_info = await self.get_sandbox(sandbox_id)
            results.append(sandbox_info)
        return results

    async def start_sandbox(self, user_id: UUID, sandbox_spec_id: str) -> UUID:
        """Start a new sandbox"""
        # Get runtime image info
        sandbox_spec_service = get_default_sandbox_spec_service()
        sandbox_spec = await sandbox_spec_service.get_sandbox_spec(sandbox_spec_id)

        if sandbox_spec is None:
            raise ValueError(f"Runtime image {sandbox_spec_id} not found")

        # Generate container ID and name
        container_id = uuid4()
        container_name = self._container_name_from_id(container_id)

        # Prepare environment variables
        env_vars = sandbox_spec.initial_env.copy()

        # Prepare port mappings and add port environment variables
        port_mappings = {}
        for container_port, description in sandbox_spec.exposed_ports.items():
            host_port = self._find_unused_port()
            port_mappings[container_port] = host_port
            # Add port as environment variable
            env_var_name = f"PORT_{container_port}"
            env_vars[env_var_name] = str(host_port)

        # Prepare labels
        labels = {
            "user_id": str(user_id),
            "sandbox_spec_id": sandbox_spec_id,
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
            container = self._client.containers.run(
                image=sandbox_spec_id,
                command=sandbox_spec.command,
                name=container_name,
                environment=env_vars,
                ports=port_mappings,
                volumes=volumes,
                working_dir=sandbox_spec.working_dir,
                labels=labels,
                detach=True,
                remove=False,
            )

            return container_id

        except APIError as e:
            raise SandboxError(f"Failed to start container: {e}")

    async def resume_sandbox(self, id: UUID) -> bool:
        """Resume a paused sandbox"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._client.containers.get(container_name)

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
            container = self._client.containers.get(container_name)

            if container.status == "running":
                container.pause()

            return True
        except (NotFound, APIError):
            return False

    async def delete_sandbox(self, id: UUID) -> bool:
        """Delete a sandbox"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._client.containers.get(container_name)

            # Stop the container if it's running
            if container.status in ["running", "paused"]:
                container.stop(timeout=10)

            # Remove the container
            container.remove()

            # Remove associated volume
            try:
                volume_name = f"openhands-workspace-{id}"
                volume = self._client.volumes.get(volume_name)
                volume.remove()
            except (NotFound, APIError):
                # Volume might not exist or already removed
                pass

            return True
        except (NotFound, APIError):
            return False

    async def __aenter__(self):
        """Start using this sandbox service"""
        self._client = docker.from_env()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop using this sandbox service"""
        self._client = None

    @classmethod
    def get_instance(cls) -> "SandboxService":
        """Get an instance of sandbox service"""
        return cls()
