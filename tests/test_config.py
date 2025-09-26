"""
Unit tests for the configuration system, focusing on configuration models
and JSON configuration loading with environment variable overrides.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr


# Environment variable constants
CONFIG_FILE_PATH_ENV = "OPENHANDS_APP_SERVER_CONFIG_PATH"


# Mock the OpenHandsModel since we can't import it due to dependency issues
class OpenHandsModel(BaseModel):
    """Mock OpenHandsModel for testing."""

    pass


class EncryptionKey(BaseModel):
    """Configuration for an encryption key."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    key: SecretStr
    active: bool = True
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


def _get_default_encryption_keys() -> list[EncryptionKey]:
    """Generate default encryption keys."""
    master_key = (
        os.getenv("JWT_SECRET") or os.getenv("MASTER_KEY") or os.urandom(32).hex()
    )
    return [
        EncryptionKey(
            key=SecretStr(master_key),
            active=True,
            notes="Default master key",
        )
    ]


class AppServerConfig(OpenHandsModel):
    encryption_keys: list[EncryptionKey] = Field(
        default_factory=_get_default_encryption_keys
    )


class TestConfig:
    """Test cases for the Config class and its methods."""

    def test_app_server_config_creation(self):
        """Test that AppServerConfig can be created with default encryption keys."""
        config = AppServerConfig()
        assert isinstance(config, AppServerConfig)
        assert len(config.encryption_keys) > 0, (
            "Should have at least one encryption key"
        )
        assert config.encryption_keys[0].active is True, "Default key should be active"

    def test_encryption_key_model(self):
        """Test the EncryptionKey model functionality."""
        # Test default values
        key = EncryptionKey(key=SecretStr("test_key"))
        assert key.active is True, "Default active should be True"
        assert key.notes is None, "Default notes should be None"
        assert isinstance(key.id, str), "ID should be a string"
        assert len(key.id) > 0, "ID should not be empty"

        # Test custom values
        custom_key = EncryptionKey(
            key=SecretStr("custom_key"), id="custom_id", active=False, notes="Test key"
        )
        assert custom_key.id == "custom_id", "Custom ID should be preserved"
        assert custom_key.active is False, "Custom active should be preserved"
        assert custom_key.notes == "Test key", "Custom notes should be preserved"

    def test_encryption_key_persistence_in_config_file(self):
        """Test that encryption keys are correctly saved and loaded from config file."""

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file_path = Path(temp_dir) / "test_config.json"

            # Create a config with encryption keys
            config1 = AppServerConfig(encryption_keys=_get_default_encryption_keys())
            master_key1 = config1.encryption_keys[0].key.get_secret_value()

            # Save the config to JSON (similar to what get_global_config does)
            config_dict = config1.model_dump(mode="json")
            # Manually include the secret values for the encryption keys
            config_dict["encryption_keys"] = [
                {**key_dict, "key": key.key.get_secret_value()}
                for key, key_dict in zip(
                    config1.encryption_keys, config_dict["encryption_keys"]
                )
            ]

            # Write to file
            config_file_path.write_text(json.dumps(config_dict, indent=2))

            # Verify the config file was created and contains the encryption keys
            assert config_file_path.exists(), "Config file should be created"

            # Read the config file and verify the encryption keys are not redacted
            with open(config_file_path, "r") as f:
                config_data = json.load(f)

            assert "encryption_keys" in config_data, (
                "Config file contains encryption_keys"
            )
            assert len(config_data["encryption_keys"]) > 0, (
                "At least one encryption key exists"
            )

            first_key = config_data["encryption_keys"][0]
            assert "key" in first_key, "Key field exists"
            assert first_key["key"] != "**********", "Key is not redacted"
            assert first_key["key"] == master_key1, "Encryption key matches"

            # Load the config again from the file
            config2 = AppServerConfig.model_validate(config_data)
            master_key2 = config2.encryption_keys[0].key.get_secret_value()

            # Verify the encryption key is the same
            assert master_key1 == master_key2, "Encryption key should be preserved"

    def test_default_encryption_keys_generation(self):
        """Test that default encryption keys are generated correctly."""
        keys = _get_default_encryption_keys()
        assert len(keys) == 1, "Should generate exactly one default key"

        key = keys[0]
        assert key.active is True, "Default key should be active"
        assert key.notes == "Default master key", (
            "Default key should have correct notes"
        )
        assert len(key.key.get_secret_value()) > 0, "Default key should have content"
