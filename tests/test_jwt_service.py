import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict

import jwt
import pytest
from jose import jwe
from jose.constants import ALGORITHMS
from pydantic import SecretStr


class MockEncryptionKey:
    """Mock EncryptionKey for testing."""

    def __init__(
        self, key: str, id: str = None, notes: str = None, created_at: datetime = None, active: bool = True
    ):
        from uuid import uuid4

        self.id = id or str(uuid4())
        self.key = SecretStr(key)
        self.notes = notes
        self.created_at = created_at or datetime.utcnow()
        self.active = active


class JWTService:
    """Service for signing/verifying JWS tokens and encrypting/decrypting JWE tokens."""

    def __init__(self, keys):
        """Initialize the JWT service with a list of keys.

        Args:
            keys: List of EncryptionKey objects. If None, will try to load from config.

        Raises:
            ValueError: If no keys are provided and config is not available
        """
        active_keys = [key for key in keys if key.active]
        if not active_keys:
            raise ValueError("At least one active key is required")

        # Store keys by ID for quick lookup
        self._keys = {key.id: key for key in keys}

        # Find the newest key as default
        newest_key = max(active_keys, key=lambda k: k.created_at)
        self._default_key_id = newest_key.id

    @property
    def default_key_id(self) -> str:
        """Get the default key ID."""
        return self._default_key_id

    def create_jws_token(
        self,
        payload: Dict[str, Any],
        key_id: str | None = None,
        expires_in: timedelta | None = None,
    ) -> str:
        """Create a JWS (JSON Web Signature) token.

        Args:
            payload: The JWT payload
            key_id: The key ID to use for signing. If None, uses the newest key.
            expires_in: Token expiration time. If None, defaults to 1 hour.

        Returns:
            The signed JWS token

        Raises:
            ValueError: If key_id is invalid
        """
        if key_id is None:
            key_id = self._default_key_id

        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")

        # Add standard JWT claims
        now = datetime.utcnow()
        if expires_in is None:
            expires_in = timedelta(hours=1)

        jwt_payload = {**payload, "iat": now, "exp": now + expires_in}

        # Use the raw key for JWT signing with key_id in header
        secret_key = self._keys[key_id].key.get_secret_value()

        return jwt.encode(
            jwt_payload, secret_key, algorithm="HS256", headers={"kid": key_id}
        )

    def verify_jws_token(self, token: str, key_id: str | None = None) -> Dict[str, Any]:
        """Verify and decode a JWS token.

        Args:
            token: The JWS token to verify
            key_id: The key ID to use for verification. If None, extracts from
                    token's kid header.

        Returns:
            The decoded JWT payload

        Raises:
            ValueError: If token is invalid or key_id is not found
            jwt.InvalidTokenError: If token verification fails
        """
        if key_id is None:
            # Try to extract key_id from the token's kid header
            try:
                unverified_header = jwt.get_unverified_header(token)
                key_id = unverified_header.get("kid")
                if not key_id:
                    raise ValueError("Token does not contain 'kid' header with key ID")
            except jwt.DecodeError:
                raise ValueError("Invalid JWT token format")

        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")

        # Use the raw key for JWT verification
        secret_key = self._keys[key_id].key.get_secret_value()

        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")

    def create_jwe_token(
        self,
        payload: Dict[str, Any],
        key_id: str | None = None,
        expires_in: timedelta | None = None,
    ) -> str:
        """Create a JWE (JSON Web Encryption) token.

        Args:
            payload: The JWT payload to encrypt
            key_id: The key ID to use for encryption. If None, uses the newest key.
            expires_in: Token expiration time. If None, defaults to 1 hour.

        Returns:
            The encrypted JWE token

        Raises:
            ValueError: If key_id is invalid
        """
        if key_id is None:
            key_id = self._default_key_id

        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")

        # Add standard JWT claims
        now = datetime.utcnow()
        if expires_in is None:
            expires_in = timedelta(hours=1)

        jwt_payload = {
            **payload,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_in).timestamp()),
        }

        # Get the raw key for JWE encryption and derive a 256-bit key
        secret_key = self._keys[key_id].key.get_secret_value()
        key_bytes = secret_key.encode() if isinstance(secret_key, str) else secret_key
        # Derive a 256-bit key using SHA256
        key_256 = hashlib.sha256(key_bytes).digest()

        # Encrypt the payload (convert to JSON string first)
        payload_json = json.dumps(jwt_payload)
        encrypted_token = jwe.encrypt(
            payload_json,
            key_256,
            algorithm=ALGORITHMS.DIR,
            encryption=ALGORITHMS.A256GCM,
            kid=key_id,
        )
        # Ensure we return a string
        return (
            encrypted_token.decode("utf-8")
            if isinstance(encrypted_token, bytes)
            else encrypted_token
        )

    def decrypt_jwe_token(
        self, token: str, key_id: str | None = None
    ) -> Dict[str, Any]:
        """Decrypt and decode a JWE token.

        Args:
            token: The JWE token to decrypt
            key_id: The key ID to use for decryption. If None, extracts
                    from token header.

        Returns:
            The decrypted JWT payload

        Raises:
            ValueError: If token is invalid or key_id is not found
            Exception: If token decryption fails
        """
        if key_id is None:
            # Try to extract key_id from the token's header
            try:
                header = jwe.get_unverified_header(token)
                key_id = header.get("kid")
                if not key_id:
                    raise ValueError("Token does not contain 'kid' header with key ID")
            except Exception:
                raise ValueError("Invalid JWE token format")

        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")

        # Get the raw key for JWE decryption and derive a 256-bit key
        secret_key = self._keys[key_id].key.get_secret_value()
        key_bytes = secret_key.encode() if isinstance(secret_key, str) else secret_key
        # Derive a 256-bit key using SHA256
        key_256 = hashlib.sha256(key_bytes).digest()

        try:
            payload_json = jwe.decrypt(token, key_256)
            assert payload_json is not None
            # Parse the JSON string back to dictionary
            payload = json.loads(payload_json)
            return payload
        except Exception as e:
            raise Exception(f"Token decryption failed: {str(e)}")


class TestJWTService:
    """Test cases for JWTService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.keys = [
            MockEncryptionKey(
                "test_key_1", "key1", "First test key", datetime(2023, 1, 1)
            ),
            MockEncryptionKey(
                "test_key_2", "key2", "Second test key", datetime(2023, 1, 2)
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
        with pytest.raises(ValueError, match="At least one active key is required"):
            JWTService([])

    def test_initialization_no_active_keys(self):
        """Test service initialization fails with no active keys."""
        inactive_keys = [
            MockEncryptionKey(
                "test_key_1", "key1", "First test key", datetime(2023, 1, 1), active=False
            ),
        ]
        with pytest.raises(ValueError, match="At least one active key is required"):
            JWTService(inactive_keys)

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
