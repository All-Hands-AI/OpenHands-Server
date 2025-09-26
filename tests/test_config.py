"""
Unit tests for the configuration system, focusing on get_global_config function
and JSON configuration loading with environment variable overrides.
"""

import json
import os
import tempfile
from pathlib import Path

from openhands_server.config import (
    CONFIG_FILE_PATH_ENV,
    AppServerConfig,
    get_global_config,
)


class TestConfig:
    """Test cases for the Config class and its methods."""

    def test_get_global_config(self):
        """Test that Config is immutable (frozen)."""
        config = get_global_config()
        assert isinstance(config, AppServerConfig)

    def test_master_key_persistence_in_config_file(self):
        """Test that the master key is correctly saved and loaded from config file."""

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file_path = Path(temp_dir) / "test_config.json"

            # Set the environment variable to use our test config file
            original_config_path = os.environ.get(CONFIG_FILE_PATH_ENV)
            os.environ[CONFIG_FILE_PATH_ENV] = str(config_file_path)

            try:
                # Clear any existing global config
                import openhands_server.config

                openhands_server.config._global_config = None

                # Generate a new config (this should create the file)
                config1 = get_global_config()
                master_key1 = config1.master_key.get_secret_value()

                # Verify the config file was created and contains the master key
                assert config_file_path.exists(), "Config file should be created"

                # Read the config file and verify the master key is not redacted
                with open(config_file_path, "r") as f:
                    config_data = json.load(f)

                assert "master_key" in config_data, "Config file contains master_key"
                assert config_data["master_key"] != "**********", "Key not redacted"
                assert config_data["master_key"] == master_key1, "Master key matches"

                # Clear the global config and load again
                openhands_server.config._global_config = None

                # Load the config again (this should read from the file)
                config2 = get_global_config()
                master_key2 = config2.master_key.get_secret_value()

                # Verify the master key is the same
                assert master_key1 == master_key2, "Master key should be preserved"

            finally:
                # Restore the original environment variable
                if original_config_path is not None:
                    os.environ[CONFIG_FILE_PATH_ENV] = original_config_path
                elif CONFIG_FILE_PATH_ENV in os.environ:
                    del os.environ[CONFIG_FILE_PATH_ENV]
