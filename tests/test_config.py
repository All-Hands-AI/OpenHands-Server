"""
Unit tests for the configuration system, focusing on get_global_config function
and JSON configuration loading with environment variable overrides.
"""

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
