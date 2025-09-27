"""
Unit tests for the configuration system, focusing on get_global_config function
and JSON configuration loading with environment variable overrides.
"""

import os

import openhands_server.config
from openhands_server.config import (
    AppServerConfig,
    get_global_config,
)


class TestConfig:
    """Test cases for the Config class and its methods."""

    def test_get_global_config(self):
        """Test that Config is immutable (frozen)."""
        config = get_global_config()
        assert isinstance(config, AppServerConfig)

    def test_web_url_default(self):
        """Test that web_url has the correct default value."""
        config = get_global_config()
        assert config.web_url == "http://localhost:3000"

    def test_web_url_from_environment(self):
        """Test that web_url can be set via OH_WEB_URL environment variable."""
        original_web_url = os.environ.get("OH_WEB_URL")

        try:
            # Clear any existing global config
            openhands_server.config._global_config = None

            # Test OH_WEB_URL override
            os.environ["OH_WEB_URL"] = "https://example.com:8080"
            config = get_global_config()
            assert config.web_url == "https://example.com:8080"

        finally:
            # Restore original environment variables
            openhands_server.config._global_config = None
            if original_web_url is not None:
                os.environ["OH_WEB_URL"] = original_web_url
            elif "OH_WEB_URL" in os.environ:
                del os.environ["OH_WEB_URL"]
