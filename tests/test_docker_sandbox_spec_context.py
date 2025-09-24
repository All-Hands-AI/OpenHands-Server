import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from openhands_server.sandbox_spec.docker_sandbox_spec_context import DockerSandboxSpecContext
from openhands_server.sandbox_spec.sandbox_spec_models import SandboxSpecInfo, SandboxSpecInfoPage


class TestDockerSandboxSpecContext:
    """Test cases for DockerSandboxSpecContext"""

    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client"""
        client = Mock()
        return client

    @pytest.fixture
    def mock_docker_image(self):
        """Create a mock Docker image"""
        image = Mock()
        image.tags = ["ghcr.io/all-hands-ai/runtime:latest"]
        image.id = "sha256:abcdef123456"
        image.attrs = {
            "Created": "2023-01-01T12:00:00.000000000Z"
        }
        return image

    @pytest.fixture
    def context(self, mock_docker_client):
        """Create a DockerSandboxSpecContext instance with mocked client"""
        return DockerSandboxSpecContext(
            client=mock_docker_client,
            repository="ghcr.io/all-hands-ai/runtime",
            command="python -u -m openhands_server.runtime",
            initial_env={"TEST_VAR": "test_value"},
            working_dir="/openhands/code"
        )

    def test_docker_image_to_sandbox_specs_with_tags(self, context, mock_docker_image):
        """Test converting Docker image with tags to SandboxSpecInfo"""
        result = context._docker_image_to_sandbox_specs(mock_docker_image)
        
        assert isinstance(result, SandboxSpecInfo)
        assert result.id == "ghcr.io/all-hands-ai/runtime:latest"
        assert result.command == "python -u -m openhands_server.runtime"
        assert result.initial_env == {"TEST_VAR": "test_value"}
        assert result.working_dir == "/openhands/code"
        assert isinstance(result.created_at, datetime)

    def test_docker_image_to_sandbox_specs_without_tags(self, context):
        """Test converting Docker image without tags to SandboxSpecInfo"""
        image = Mock()
        image.tags = []
        image.id = "sha256:abcdef123456"
        image.attrs = {"Created": "2023-01-01T12:00:00.000000000Z"}
        
        result = context._docker_image_to_sandbox_specs(image)
        
        assert result.id == "sha256:abcde"  # Should use first 12 characters of image ID

    def test_docker_image_to_sandbox_specs_invalid_date(self, context):
        """Test converting Docker image with invalid creation date"""
        image = Mock()
        image.tags = ["ghcr.io/all-hands-ai/runtime:latest"]
        image.id = "sha256:abcdef123456"
        image.attrs = {"Created": "invalid-date"}
        
        result = context._docker_image_to_sandbox_specs(image)
        
        # Should use current time when date parsing fails
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_search_sandbox_specs_success(self, context, mock_docker_image):
        """Test successful search for sandbox specs"""
        context.client.images.list.return_value = [mock_docker_image]
        
        result = await context.search_sandbox_specs()
        
        assert isinstance(result, SandboxSpecInfoPage)
        assert len(result.items) == 1
        assert result.items[0].id == "ghcr.io/all-hands-ai/runtime:latest"
        assert result.next_page_id is None
        context.client.images.list.assert_called_once_with(name="ghcr.io/all-hands-ai/runtime")

    @pytest.mark.asyncio
    async def test_search_sandbox_specs_with_pagination(self, context):
        """Test search with pagination"""
        # Create multiple mock images
        images = []
        for i in range(5):
            image = Mock()
            image.tags = [f"ghcr.io/all-hands-ai/runtime:v{i}"]
            image.id = f"sha256:abcdef12345{i}"
            image.attrs = {"Created": "2023-01-01T12:00:00.000000000Z"}
            images.append(image)
        
        context.client.images.list.return_value = images
        
        # Test first page
        result = await context.search_sandbox_specs(limit=2)
        assert len(result.items) == 2
        assert result.next_page_id == "2"
        
        # Test second page
        result = await context.search_sandbox_specs(page_id="2", limit=2)
        assert len(result.items) == 2
        assert result.next_page_id == "4"
        
        # Test last page
        result = await context.search_sandbox_specs(page_id="4", limit=2)
        assert len(result.items) == 1
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_sandbox_specs_api_error(self, context):
        """Test search when Docker API returns an error"""
        from docker.errors import APIError
        context.client.images.list.side_effect = APIError("Docker error")
        
        result = await context.search_sandbox_specs()
        
        assert isinstance(result, SandboxSpecInfoPage)
        assert len(result.items) == 0
        assert result.next_page_id is None

    @pytest.mark.asyncio
    async def test_search_sandbox_specs_filters_by_repository(self, context):
        """Test that search filters images by repository"""
        # Create images with different repositories
        matching_image = Mock()
        matching_image.tags = ["ghcr.io/all-hands-ai/runtime:latest"]
        matching_image.id = "sha256:abcdef123456"
        matching_image.attrs = {"Created": "2023-01-01T12:00:00.000000000Z"}
        
        non_matching_image = Mock()
        non_matching_image.tags = ["other-repo:latest"]
        non_matching_image.id = "sha256:fedcba654321"
        non_matching_image.attrs = {"Created": "2023-01-01T12:00:00.000000000Z"}
        
        context.client.images.list.return_value = [matching_image, non_matching_image]
        
        result = await context.search_sandbox_specs()
        
        # Should only include the matching image
        assert len(result.items) == 1
        assert result.items[0].id == "ghcr.io/all-hands-ai/runtime:latest"

    @pytest.mark.asyncio
    async def test_get_sandbox_spec_success(self, context, mock_docker_image):
        """Test successful retrieval of a single sandbox spec"""
        context.client.images.get.return_value = mock_docker_image
        
        result = await context.get_sandbox_spec("ghcr.io/all-hands-ai/runtime:latest")
        
        assert isinstance(result, SandboxSpecInfo)
        assert result.id == "ghcr.io/all-hands-ai/runtime:latest"
        context.client.images.get.assert_called_once_with("ghcr.io/all-hands-ai/runtime:latest")

    @pytest.mark.asyncio
    async def test_get_sandbox_spec_not_found(self, context):
        """Test retrieval of non-existent sandbox spec"""
        from docker.errors import NotFound
        context.client.images.get.side_effect = NotFound("Image not found")
        
        result = await context.get_sandbox_spec("non-existent:latest")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sandbox_spec_api_error(self, context):
        """Test retrieval when Docker API returns an error"""
        from docker.errors import APIError
        context.client.images.get.side_effect = APIError("Docker error")
        
        result = await context.get_sandbox_spec("some-image:latest")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_get_sandbox_specs(self, context, mock_docker_image):
        """Test batch retrieval of sandbox specs"""
        # Mock get_sandbox_spec method
        context.get_sandbox_spec = AsyncMock()
        context.get_sandbox_spec.side_effect = [
            SandboxSpecInfo(
                id="image1:latest",
                command="test-command",
                created_at=datetime.now(),
                initial_env={},
                working_dir="/test"
            ),
            None,  # Second image not found
            SandboxSpecInfo(
                id="image3:latest",
                command="test-command",
                created_at=datetime.now(),
                initial_env={},
                working_dir="/test"
            )
        ]
        
        result = await context.batch_get_sandbox_specs(["image1:latest", "image2:latest", "image3:latest"])
        
        assert len(result) == 3
        assert result[0] is not None
        assert result[0].id == "image1:latest"
        assert result[1] is None
        assert result[2] is not None
        assert result[2].id == "image3:latest"

    @pytest.mark.asyncio
    async def test_context_manager_with_existing_client(self, mock_docker_client):
        """Test async context manager when client is already provided"""
        context = DockerSandboxSpecContext(client=mock_docker_client)
        
        async with context as ctx:
            assert ctx is context
            assert ctx.client is mock_docker_client

    @pytest.mark.asyncio
    @patch('docker.from_env')
    async def test_context_manager_creates_client(self, mock_from_env):
        """Test async context manager creates client when none provided"""
        mock_client = Mock()
        mock_from_env.return_value = mock_client
        
        context = DockerSandboxSpecContext()
        
        async with context as ctx:
            assert ctx is context
            assert ctx.client is mock_client
            mock_from_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance(self):
        """Test get_instance class method"""
        instance = await DockerSandboxSpecContext.get_instance(
            repository="test-repo",
            command="test-command"
        )
        
        assert isinstance(instance, DockerSandboxSpecContext)
        assert instance.repository == "test-repo"
        assert instance.command == "test-command"

    @pytest.mark.asyncio
    async def test_get_default_sandbox_spec(self, context, mock_docker_image):
        """Test getting default sandbox spec"""
        context.client.images.list.return_value = [mock_docker_image]
        
        result = await context.get_default_sandbox_spec()
        
        assert isinstance(result, SandboxSpecInfo)
        assert result.id == "ghcr.io/all-hands-ai/runtime:latest"

    @pytest.mark.asyncio
    async def test_get_default_sandbox_spec_empty_list(self, context):
        """Test getting default sandbox spec when no images available"""
        context.client.images.list.return_value = []
        
        with pytest.raises(IndexError):
            await context.get_default_sandbox_spec()