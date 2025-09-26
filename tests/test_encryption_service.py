import json
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

# Create standalone EncryptionKey for testing
class EncryptionKey:
    def __init__(self, key: str, id: str = None, use_for_encryption: bool = True, notes: str = None, created_at: datetime = None):
        self.id = id or str(uuid4())
        self.key = SecretStr(key)
        self.use_for_encryption = use_for_encryption
        self.notes = notes
        self.created_at = created_at or datetime.utcnow()

# Import the service with a mock for testing
import sys
from unittest.mock import MagicMock

# Mock the config module
mock_config = MagicMock()
sys.modules['openhands_server.config'] = mock_config

from openhands_server.services.encryption_service import EncryptionService


class TestEncryptionService:
    """Test cases for the enhanced EncryptionService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.key1 = EncryptionKey("test_key_1", "key1", True, "First test key", datetime(2023, 1, 1))
        self.key2 = EncryptionKey("test_key_2", "key2", True, "Second test key", datetime(2023, 1, 2))
        self.key3 = EncryptionKey("test_key_3", "key3", False, "Disabled key", datetime(2023, 1, 3))
        
        self.service = EncryptionService([self.key1, self.key2, self.key3])

    def test_initialization_with_keys(self):
        """Test service initialization with provided keys."""
        service = EncryptionService([self.key1, self.key2])
        assert len(service._keys) == 2
        assert service.default_key_id == "key2"  # Newest encryption key

    def test_initialization_no_keys(self):
        """Test service initialization fails with no keys."""
        with pytest.raises(ValueError, match="At least one encryption key must be provided"):
            EncryptionService([])

    def test_initialization_no_encryption_keys(self):
        """Test service initialization fails with no encryption-enabled keys."""
        disabled_key = EncryptionKey("test", use_for_encryption=False)
        with pytest.raises(ValueError, match="At least one key must be marked for encryption"):
            EncryptionService([disabled_key])

    def test_encrypt_decrypt_with_default_key(self):
        """Test encryption and decryption with default key."""
        original_text = "Hello, World!"
        
        # Encrypt with default key
        encrypted_data = self.service.encrypt(original_text)
        assert isinstance(encrypted_data, dict)
        assert 'encrypted_text' in encrypted_data
        assert 'key_id' in encrypted_data
        assert encrypted_data['key_id'] == "key2"  # Newest key
        
        # Decrypt
        decrypted_text = self.service.decrypt(encrypted_data)
        assert decrypted_text == original_text

    def test_encrypt_decrypt_with_specific_key(self):
        """Test encryption and decryption with specific key."""
        original_text = "Hello, World!"
        
        # Encrypt with specific key
        encrypted_data = self.service.encrypt(original_text, key_id="key1")
        assert encrypted_data['key_id'] == "key1"
        
        # Decrypt
        decrypted_text = self.service.decrypt(encrypted_data)
        assert decrypted_text == original_text

    def test_encrypt_with_disabled_key(self):
        """Test encryption fails with disabled key."""
        with pytest.raises(ValueError, match="Key ID 'key3' is not marked for encryption"):
            self.service.encrypt("test", key_id="key3")

    def test_encrypt_with_invalid_key(self):
        """Test encryption fails with invalid key ID."""
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.encrypt("test", key_id="invalid")

    def test_decrypt_legacy_format(self):
        """Test decryption of legacy string format."""
        original_text = "Hello, World!"
        
        # Encrypt to get the encrypted text
        encrypted_data = self.service.encrypt(original_text, key_id="key1")
        encrypted_text = encrypted_data['encrypted_text']
        
        # Decrypt using legacy format (string + key_id)
        decrypted_text = self.service.decrypt(encrypted_text, key_id="key1")
        assert decrypted_text == original_text

    def test_decrypt_legacy_format_no_key_id(self):
        """Test decryption of legacy format fails without key_id."""
        with pytest.raises(ValueError, match="key_id is required when encrypted_data is a string"):
            self.service.decrypt("some_encrypted_text")

    def test_decrypt_invalid_key(self):
        """Test decryption fails with invalid key ID."""
        encrypted_data = {'encrypted_text': 'test', 'key_id': 'invalid'}
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.decrypt(encrypted_data)

    def test_decrypt_invalid_data_format(self):
        """Test decryption fails with invalid data format."""
        with pytest.raises(ValueError, match="encrypted_data must be a string or dict"):
            self.service.decrypt(123)

    def test_decrypt_invalid_dict_format(self):
        """Test decryption fails with invalid dict format."""
        with pytest.raises(ValueError, match="encrypted_data dict must contain 'encrypted_text' and 'key_id'"):
            self.service.decrypt({'invalid': 'data'})

    def test_is_encrypted_dict_format(self):
        """Test is_encrypted with dict format."""
        original_text = "Hello, World!"
        encrypted_data = self.service.encrypt(original_text)
        
        assert self.service.is_encrypted(encrypted_data) is True
        assert self.service.is_encrypted({'encrypted_text': 'invalid', 'key_id': 'key1'}) is False

    def test_is_encrypted_legacy_format(self):
        """Test is_encrypted with legacy string format."""
        original_text = "Hello, World!"
        encrypted_data = self.service.encrypt(original_text, key_id="key1")
        encrypted_text = encrypted_data['encrypted_text']
        
        assert self.service.is_encrypted(encrypted_text, key_id="key1") is True
        assert self.service.is_encrypted("invalid_data", key_id="key1") is False

    def test_create_jwt_token_default_key(self):
        """Test JWT token creation with default key."""
        payload = {'user_id': 123, 'role': 'admin'}
        token = self.service.create_jwt_token(payload)
        
        assert isinstance(token, str)
        
        # Check header for kid
        header = jwt.get_unverified_header(token)
        assert header['kid'] == 'key2'  # Default key
        
        # Decode without verification to check structure
        unverified = jwt.decode(token, options={"verify_signature": False})
        assert unverified['user_id'] == 123
        assert unverified['role'] == 'admin'
        assert 'iat' in unverified
        assert 'exp' in unverified
        assert 'iss' not in unverified  # Should not have iss claim

    def test_create_jwt_token_specific_key(self):
        """Test JWT token creation with specific key."""
        payload = {'user_id': 123}
        token = self.service.create_jwt_token(payload, key_id="key1")
        
        header = jwt.get_unverified_header(token)
        assert header['kid'] == 'key1'

    def test_create_jwt_token_custom_expiration(self):
        """Test JWT token creation with custom expiration."""
        payload = {'user_id': 123}
        expires_in = timedelta(minutes=30)
        token = self.service.create_jwt_token(payload, expires_in=expires_in)
        
        unverified = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.utcfromtimestamp(unverified['exp'])
        iat_time = datetime.utcfromtimestamp(unverified['iat'])
        assert (exp_time - iat_time) == expires_in

    def test_create_jwt_token_invalid_key(self):
        """Test JWT token creation fails with invalid key."""
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.create_jwt_token({'test': 'data'}, key_id="invalid")

    def test_create_jwt_token_disabled_key(self):
        """Test JWT token creation fails with disabled key."""
        with pytest.raises(ValueError, match="Key ID 'key3' is not marked for encryption"):
            self.service.create_jwt_token({'test': 'data'}, key_id="key3")

    def test_verify_jwt_token_auto_key_detection(self):
        """Test JWT token verification with automatic key detection."""
        payload = {'user_id': 123, 'role': 'admin'}
        token = self.service.create_jwt_token(payload, key_id="key1")
        
        # Verify without specifying key_id (should auto-detect from kid header)
        decoded = self.service.verify_jwt_token(token)
        assert decoded['user_id'] == 123
        assert decoded['role'] == 'admin'
        assert 'iss' not in decoded  # Should not have iss claim

    def test_verify_jwt_token_specific_key(self):
        """Test JWT token verification with specific key."""
        payload = {'user_id': 123}
        token = self.service.create_jwt_token(payload, key_id="key1")
        
        # Verify with specific key_id
        decoded = self.service.verify_jwt_token(token, key_id="key1")
        assert decoded['user_id'] == 123

    def test_verify_jwt_token_wrong_key(self):
        """Test JWT token verification fails with wrong key."""
        payload = {'user_id': 123}
        token = self.service.create_jwt_token(payload, key_id="key1")
        
        # Try to verify with wrong key
        with pytest.raises(jwt.InvalidTokenError):
            self.service.verify_jwt_token(token, key_id="key2")

    def test_verify_jwt_token_invalid_key(self):
        """Test JWT token verification fails with invalid key ID."""
        token = self.service.create_jwt_token({'test': 'data'})
        
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.verify_jwt_token(token, key_id="invalid")

    def test_verify_jwt_token_no_kid_header(self):
        """Test JWT token verification fails when token has no kid header."""
        # Create token manually without kid header
        payload = {'user_id': 123}
        token = jwt.encode(payload, "some_key", algorithm='HS256')
        
        with pytest.raises(ValueError, match="Token does not contain 'kid' header with key ID"):
            self.service.verify_jwt_token(token)

    def test_verify_jwt_token_invalid_format(self):
        """Test JWT token verification fails with invalid token format."""
        with pytest.raises(ValueError, match="Invalid JWT token format"):
            self.service.verify_jwt_token("invalid.token")

    def test_get_key_info(self):
        """Test getting key information."""
        info = self.service.get_key_info("key1")
        
        assert info['id'] == 'key1'
        assert info['use_for_encryption'] is True
        assert info['notes'] == 'First test key'
        assert 'created_at' in info
        assert 'key' not in info  # Should not expose actual key

    def test_get_key_info_invalid_key(self):
        """Test getting key info fails with invalid key ID."""
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.get_key_info("invalid")

    def test_list_keys(self):
        """Test listing all keys."""
        keys = self.service.list_keys()
        
        assert len(keys) == 3
        key_ids = [key['id'] for key in keys]
        assert 'key1' in key_ids
        assert 'key2' in key_ids
        assert 'key3' in key_ids
        
        # Ensure no actual key values are exposed
        for key in keys:
            assert 'key' not in key

    def test_default_key_id_property(self):
        """Test default_key_id property."""
        assert self.service.default_key_id == "key2"  # Newest encryption key

    def test_encrypt_non_string_input(self):
        """Test encryption with non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Input must be a string"):
            self.service.encrypt(123)

    def test_unicode_text_support(self):
        """Test encryption and decryption with unicode text."""
        original_text = "Hello, 世界! 🌍"
        encrypted_data = self.service.encrypt(original_text)
        decrypted_text = self.service.decrypt(encrypted_data)
        assert decrypted_text == original_text

    def test_empty_string_support(self):
        """Test encryption and decryption with empty string."""
        original_text = ""
        encrypted_data = self.service.encrypt(original_text)
        decrypted_text = self.service.decrypt(encrypted_data)
        assert decrypted_text == original_text

    def test_long_text_support(self):
        """Test encryption and decryption with long text."""
        original_text = "A" * 10000  # 10KB of text
        encrypted_data = self.service.encrypt(original_text)
        decrypted_text = self.service.decrypt(encrypted_data)
        assert decrypted_text == original_text

    def test_different_keys_produce_different_results(self):
        """Test that different keys produce different encrypted results."""
        original_text = "Hello, World!"
        
        encrypted1 = self.service.encrypt(original_text, key_id="key1")
        encrypted2 = self.service.encrypt(original_text, key_id="key2")
        
        assert encrypted1['encrypted_text'] != encrypted2['encrypted_text']
        assert encrypted1['key_id'] != encrypted2['key_id']

    def test_cross_key_decryption_fails(self):
        """Test that keys cannot decrypt each other's data."""
        original_text = "Hello, World!"
        
        # Encrypt with key1
        encrypted_data = self.service.encrypt(original_text, key_id="key1")
        encrypted_text = encrypted_data['encrypted_text']
        
        # Try to decrypt with key2 (should fail)
        with pytest.raises(ValueError, match="Failed to decrypt text"):
            self.service.decrypt(encrypted_text, key_id="key2")