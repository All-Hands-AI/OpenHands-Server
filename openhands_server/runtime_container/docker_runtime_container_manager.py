
import asyncio
import secrets
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

import docker
from docker.errors import APIError, NotFound
from pydantic import SecretStr

from openhands_server.runtime_container.model import (
    RuntimeContainerInfo,
    RuntimeContainerPage,
    RuntimeContainerStatus,
)
from openhands_server.runtime_container.manager import (
    RuntimeContainerManager,
)
from openhands_server.runtime_image.docker_runtime_image_manager import DockerRuntimeImageManager
from openhands_server.runtime_image.manager import (
    get_default_runtime_image_manager,
)

@dataclass
class VolumeMount:
    host_path: str
    container_path: str
    mode: str = 'rw'


@dataclass
class ExposedPort:
    """Exposed port. A free port will be found for this and an environment variable set"""
    name: str
    description: str


@dataclass
class DockerRuntimeContainerManager(RuntimeContainerManager):

    client: docker.DockerClient = field(default=None)
    container_name_prefix: str = "openhands-runtime-"
    exposed_url_pattern: str = "http://localhost:{port}"
    runtime_image_manager: DockerRuntimeImageManager = field(default_factory=DockerRuntimeImageManager.get_instance)
    mounts: list[VolumeMount] = field(default_factory=list)
    exposed_port: list[ExposedPort] = field(default_factory=lambda: [
        ExposedPort("APPLICATION_SERVER_PORT", 'The port on which the application server runs within the container')
    ])

    def _get_client(self) -> docker.DockerClient:
        """Get Docker client, creating it if necessary"""
        if self.client is None:
            self.client = docker.from_env()
        return self.client

    def _find_unused_port(self) -> int:
        """Find an unused port on the host machine"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
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
        
        uuid_str = container_name[len(self.container_name_prefix):]
        try:
            return UUID(uuid_str)
        except ValueError:
            return None

    def _docker_status_to_runtime_status(self, docker_status: str) -> RuntimeContainerStatus:
        """Convert Docker container status to RuntimeContainerStatus"""
        status_mapping = {
            "running": RuntimeContainerStatus.RUNNING,
            "paused": RuntimeContainerStatus.PAUSED,
            "exited": RuntimeContainerStatus.DELETED,
            "created": RuntimeContainerStatus.STARTING,
            "restarting": RuntimeContainerStatus.STARTING,
            "removing": RuntimeContainerStatus.DELETED,
            "dead": RuntimeContainerStatus.ERROR,
        }
        return status_mapping.get(docker_status.lower(), RuntimeContainerStatus.ERROR)

    def _container_to_runtime_info(self, container) -> RuntimeContainerInfo | None:
        """Convert Docker container to RuntimeContainerInfo"""
        # Extract runtime ID from container name
        runtime_id = self._runtime_id_from_container_name(container.name)
        if runtime_id is None:
            return None

        # Get user_id and runtime_image_id from labels
        labels = container.labels or {}
        user_id_str = labels.get("user_id")
        runtime_image_id = labels.get("runtime_image_id")
        
        if not user_id_str or not runtime_image_id:
            return None

        # Convert Docker status to runtime status
        status = self._docker_status_to_runtime_status(container.status)

        # Parse creation time
        created_str = container.attrs.get("Created", "")
        try:
            created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.now()

        # Generate URL and session key for running containers
        url = None
        session_api_key = None
        
        if status == RuntimeContainerStatus.RUNNING:
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

        return RuntimeContainerInfo(
            id=runtime_id,
            user_id=user_id_str,
            runtime_image_id=runtime_image_id,
            status=status,
            url=url,
            session_api_key=session_api_key,
            created_at=created_at,
        )

    async def search_runtime_containers(
        self, user_id: UUID | None = None, page_id: str | None = None, limit: int = 100
    ) -> RuntimeContainerPage:
        """Search for runtime containers"""
        try:
            # Get all containers with our prefix
            all_containers = self._get_client().containers.list(all=True)
            runtime_containers = []

            for container in all_containers:
                if container.name.startswith(self.container_name_prefix):
                    runtime_info = self._container_to_runtime_info(container)
                    if runtime_info:
                        # Filter by user_id if specified
                        if user_id is None or runtime_info.user_id == str(user_id):
                            runtime_containers.append(runtime_info)

            # Sort by creation time (newest first)
            runtime_containers.sort(key=lambda x: x.created_at, reverse=True)

            # Apply pagination
            start_idx = 0
            if page_id:
                try:
                    start_idx = int(page_id)
                except ValueError:
                    start_idx = 0

            end_idx = start_idx + limit
            paginated_containers = runtime_containers[start_idx:end_idx]

            # Determine next page ID
            next_page_id = None
            if end_idx < len(runtime_containers):
                next_page_id = str(end_idx)

            return RuntimeContainerPage(
                items=paginated_containers, next_page_id=next_page_id
            )

        except APIError:
            return RuntimeContainerPage(items=[], next_page_id=None)

    async def get_runtime_containers(self, id: UUID) -> RuntimeContainerInfo | None:
        """Get a single runtime container info"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._get_client().containers.get(container_name)
            return self._container_to_runtime_info(container)
        except (NotFound, APIError):
            return None

    async def batch_get_runtime_containers(
        self, ids: list[UUID]
    ) -> list[RuntimeContainerInfo | None]:
        """Get a batch of runtime container info"""
        results = []
        for container_id in ids:
            result = await self.get_runtime_containers(container_id)
            results.append(result)
        return results

    async def start_runtime_container(self, user_id: UUID, runtime_image_id: str) -> UUID:
        """Start a new runtime container"""
        # Get runtime image info
        runtime_image_manager = get_default_runtime_image_manager()
        runtime_image = await runtime_image_manager.get_runtime_image(runtime_image_id)
        
        if runtime_image is None:
            raise ValueError(f"Runtime image {runtime_image_id} not found")

        # Generate container ID and name
        container_id = uuid4()
        container_name = self._container_name_from_id(container_id)

        # Prepare environment variables
        env_vars = runtime_image.initial_env.copy()
        
        # Prepare port mappings and add port environment variables
        port_mappings = {}
        for container_port, description in runtime_image.exposed_ports.items():
            host_port = self._find_unused_port()
            port_mappings[container_port] = host_port
            # Add port as environment variable
            env_var_name = f"PORT_{container_port}"
            env_vars[env_var_name] = str(host_port)

        # Prepare labels
        labels = {
            "user_id": str(user_id),
            "runtime_image_id": runtime_image_id,
        }

        # TODO: Handle mounts - for now, we'll create a basic volume mount
        volumes = {
            f"openhands-workspace-{container_id}": {
                "bind": runtime_image.working_dir,
                "mode": "rw"
            }
        }

        try:
            # Create and start the container
            container = self._get_client().containers.run(
                image=runtime_image_id,
                command=runtime_image.command,
                name=container_name,
                environment=env_vars,
                ports=port_mappings,
                volumes=volumes,
                working_dir=runtime_image.working_dir,
                labels=labels,
                detach=True,
                remove=False,
            )

            return container_id

        except APIError as e:
            raise RuntimeError(f"Failed to start container: {e}")

    async def resume_runtime_container(self, id: UUID) -> bool:
        """Resume a paused runtime container"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._get_client().containers.get(container_name)
            
            if container.status == "paused":
                container.unpause()
            elif container.status == "exited":
                container.start()
            
            return True
        except (NotFound, APIError):
            return False

    async def pause_runtime_container(self, id: UUID) -> bool:
        """Pause a running runtime container"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._get_client().containers.get(container_name)
            
            if container.status == "running":
                container.pause()
            
            return True
        except (NotFound, APIError):
            return False

    async def delete_runtime_container(self, id: UUID) -> bool:
        """Delete a runtime container"""
        try:
            container_name = self._container_name_from_id(id)
            container = self._get_client().containers.get(container_name)
            
            # Stop the container if it's running
            if container.status in ["running", "paused"]:
                container.stop(timeout=10)
            
            # Remove the container
            container.remove()
            
            # Remove associated volume
            try:
                volume_name = f"openhands-workspace-{id}"
                volume = self._get_client().volumes.get(volume_name)
                volume.remove()
            except (NotFound, APIError):
                # Volume might not exist or already removed
                pass
            
            return True
        except (NotFound, APIError):
            return False

    async def __aenter__(self):
        """Start using this runtime container manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop using this runtime container manager"""
        pass

    @classmethod
    def get_instance(cls) -> "RuntimeContainerManager":
        """Get an instance of runtime container manager"""
        return cls()
