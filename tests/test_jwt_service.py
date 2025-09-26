from datetime import datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr

from openhands_server.config import EncryptionKey
from openhands_server.services.jwt_service import JWTService


class TestJWTService:
    """Test cases for JWTService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.keys = [
            EncryptionKey(
                id="test_key_1",
                key=SecretStr("key1"),
                notes="First test key",
                created_at=datetime(2023, 1, 1),
            ),
            EncryptionKey(
                id="test_key_2",
                key=SecretStr("key2"),
                notes="Second test key",
                created_at=datetime(2023, 1, 2),
            ),
        ]
        self.service = JWTService(self.keys)

    def test_initialization_with_keys(self):
        """Test service initialization with provided keys."""
        assert len(self.service._keys) == 2
        assert "key1" in self.service._keys
        assert "key2" in self.service._keys
        assert self.service.default_key_id == "key2"  # Newest key

    def test_initialization_no_keys(self):
        """Test service initialization fails with no keys."""
        with pytest.raises(ValueError, match="At least one key is required"):
            JWTService([])

    def test_create_jws_token_default_key(self):
        """Test JWS token creation with default key."""
        payload = {"user_id": 123, "role": "admin"}
        token = self.service.create_jws_token(payload)

        assert isinstance(token, str)

        # Check header for kid
        header = jwt.get_unverified_header(token)
        assert header["kid"] == "key2"  # Default key

        # Decode without verification to check structure
        unverified = jwt.decode(token, options={"verify_signature": False})
        assert unverified["user_id"] == 123
        assert unverified["role"] == "admin"
        assert "iat" in unverified
        assert "exp" in unverified

    def test_create_jws_token_specific_key(self):
        """Test JWS token creation with specific key."""
        payload = {"user_id": 123}
        token = self.service.create_jws_token(payload, key_id="key1")

        header = jwt.get_unverified_header(token)
        assert header["kid"] == "key1"

    def test_create_jws_token_custom_expiration(self):
        """Test JWS token creation with custom expiration."""
        payload = {"user_id": 123}
        expires_in = timedelta(minutes=30)
        token = self.service.create_jws_token(payload, expires_in=expires_in)

        unverified = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.utcfromtimestamp(unverified["exp"])
        iat_time = datetime.utcfromtimestamp(unverified["iat"])

        # Check that expiration is approximately 30 minutes from issued time
        time_diff = exp_time - iat_time
        assert abs(time_diff.total_seconds() - 1800) < 5  # Within 5 seconds

    def test_create_jws_token_invalid_key(self):
        """Test JWS token creation fails with invalid key."""
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.create_jws_token({"test": "data"}, key_id="invalid")

    def test_verify_jws_token_auto_key_detection(self):
        """Test JWS token verification with automatic key detection."""
        payload = {"user_id": 123, "role": "admin"}
        token = self.service.create_jws_token(payload, key_id="key1")

        # Verify without specifying key_id (should auto-detect from kid header)
        decoded = self.service.verify_jws_token(token)
        assert decoded["user_id"] == 123
        assert decoded["role"] == "admin"

    def test_verify_jws_token_specific_key(self):
        """Test JWS token verification with specific key."""
        payload = {"user_id": 123}
        token = self.service.create_jws_token(payload, key_id="key1")

        # Verify with explicit key_id
        decoded = self.service.verify_jws_token(token, key_id="key1")
        assert decoded["user_id"] == 123

    def test_verify_jws_token_wrong_key(self):
        """Test JWS token verification fails with wrong key."""
        payload = {"user_id": 123}
        token = self.service.create_jws_token(payload, key_id="key1")

        # Try to verify with wrong key
        with pytest.raises(jwt.InvalidTokenError):
            self.service.verify_jws_token(token, key_id="key2")

    def test_verify_jws_token_invalid_key(self):
        """Test JWS token verification fails with invalid key."""
        payload = {"user_id": 123}
        token = self.service.create_jws_token(payload, key_id="key1")

        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.verify_jws_token(token, key_id="invalid")

    def test_verify_jws_token_no_kid_header(self):
        """Test JWS token verification fails when token has no kid header."""
        # Create token manually without kid header
        payload = {"user_id": 123}
        token = jwt.encode(payload, "some_key", algorithm="HS256")

        with pytest.raises(
            ValueError, match="Token does not contain 'kid' header with key ID"
        ):
            self.service.verify_jws_token(token)

    def test_verify_jws_token_invalid_format(self):
        """Test JWS token verification fails with invalid token format."""
        with pytest.raises(ValueError, match="Invalid JWT token format"):
            self.service.verify_jws_token("invalid.token")

    def test_create_jwe_token_default_key(self):
        """Test JWE token creation with default key."""
        payload = {"user_id": 123, "role": "admin"}
        token = self.service.create_jwe_token(payload)

        assert isinstance(token, str)
        # JWE tokens have 5 parts separated by dots
        assert len(token.split(".")) == 5

    def test_create_jwe_token_specific_key(self):
        """Test JWE token creation with specific key."""
        payload = {"user_id": 123}
        token = self.service.create_jwe_token(payload, key_id="key1")

        assert isinstance(token, str)
        assert len(token.split(".")) == 5

    def test_create_jwe_token_invalid_key(self):
        """Test JWE token creation fails with invalid key."""
        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.create_jwe_token({"test": "data"}, key_id="invalid")

    def test_decrypt_jwe_token_auto_key_detection(self):
        """Test JWE token decryption with automatic key detection."""
        payload = {"user_id": 123, "role": "admin"}
        token = self.service.create_jwe_token(payload, key_id="key1")

        # Decrypt without specifying key_id (should auto-detect from header)
        decoded = self.service.decrypt_jwe_token(token)
        assert decoded["user_id"] == 123
        assert decoded["role"] == "admin"

    def test_decrypt_jwe_token_specific_key(self):
        """Test JWE token decryption with specific key."""
        payload = {"user_id": 123}
        token = self.service.create_jwe_token(payload, key_id="key1")

        # Decrypt with explicit key_id
        decoded = self.service.decrypt_jwe_token(token, key_id="key1")
        assert decoded["user_id"] == 123

    def test_decrypt_jwe_token_wrong_key(self):
        """Test JWE token decryption fails with wrong key."""
        payload = {"user_id": 123}
        token = self.service.create_jwe_token(payload, key_id="key1")

        # Try to decrypt with wrong key
        with pytest.raises(Exception, match="Token decryption failed"):
            self.service.decrypt_jwe_token(token, key_id="key2")

    def test_decrypt_jwe_token_invalid_key(self):
        """Test JWE token decryption fails with invalid key."""
        payload = {"user_id": 123}
        token = self.service.create_jwe_token(payload, key_id="key1")

        with pytest.raises(ValueError, match="Key ID 'invalid' not found"):
            self.service.decrypt_jwe_token(token, key_id="invalid")

    def test_default_key_id_property(self):
        """Test default_key_id property."""
        assert self.service.default_key_id == "key2"  # Newest key

    def test_jws_jwe_round_trip(self):
        """Test that JWS and JWE tokens work independently."""
        payload = {"user_id": 123, "role": "admin", "permissions": ["read", "write"]}

        # Create and verify JWS token
        jws_token = self.service.create_jws_token(payload)
        jws_decoded = self.service.verify_jws_token(jws_token)

        # Create and decrypt JWE token
        jwe_token = self.service.create_jwe_token(payload)
        jwe_decoded = self.service.decrypt_jwe_token(jwe_token)

        # Both should contain the same user data
        assert jws_decoded["user_id"] == jwe_decoded["user_id"] == 123
        assert jws_decoded["role"] == jwe_decoded["role"] == "admin"
        assert (
            jws_decoded["permissions"]
            == jwe_decoded["permissions"]
            == ["read", "write"]
        )

    def test_token_expiration(self):
        """Test that tokens include proper expiration claims."""
        payload = {"user_id": 123}
        expires_in = timedelta(minutes=15)

        # Test JWS token expiration
        jws_token = self.service.create_jws_token(payload, expires_in=expires_in)
        jws_decoded = self.service.verify_jws_token(jws_token)

        exp_time = datetime.utcfromtimestamp(jws_decoded["exp"])
        iat_time = datetime.utcfromtimestamp(jws_decoded["iat"])
        time_diff = exp_time - iat_time

        assert (
            abs(time_diff.total_seconds() - 900) < 5
        )  # Within 5 seconds of 15 minutes

        # Test JWE token expiration
        jwe_token = self.service.create_jwe_token(payload, expires_in=expires_in)
        jwe_decoded = self.service.decrypt_jwe_token(jwe_token)

        exp_time = datetime.utcfromtimestamp(jwe_decoded["exp"])
        iat_time = datetime.utcfromtimestamp(jwe_decoded["iat"])
        time_diff = exp_time - iat_time

        assert (
            abs(time_diff.total_seconds() - 900) < 5
        )  # Within 5 seconds of 15 minutes
