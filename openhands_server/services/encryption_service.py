import base64
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Union, TYPE_CHECKING

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import config only when needed to avoid dependency issues in standalone usage
try:
    from openhands_server.config import EncryptionKey, get_global_config
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False

if TYPE_CHECKING:
    from openhands_server.config import EncryptionKey


class EncryptionService:
    """Service for encrypting and decrypting text using multiple keys with JWT support."""

    def __init__(self, keys: list['EncryptionKey'] | None = None):
        """Initialize the encryption service with a list of keys.
        
        Args:
            keys: List of EncryptionKey objects. If None, will try to load from config.
        """
        if keys is None:
            if not _CONFIG_AVAILABLE:
                raise ImportError(
                    "OpenHands config module is not available. "
                    "Either provide keys directly or ensure the full OpenHands environment is set up."
                )
            config = get_global_config()
            keys = config.encryption_keys
        
        if not keys:
            raise ValueError("At least one encryption key must be provided")
        
        self._keys = {key.id: key for key in keys}
        self._fernet_cache: Dict[str, Fernet] = {}
        
        # Find the newest key for default encryption
        encryption_keys = [key for key in keys if key.use_for_encryption]
        if not encryption_keys:
            raise ValueError("At least one key must be marked for encryption")
        
        self._default_key_id = max(encryption_keys, key=lambda k: k.created_at).id

    def _get_fernet(self, key_id: str) -> Fernet:
        """Get or create a Fernet instance for the given key ID."""
        if key_id not in self._fernet_cache:
            if key_id not in self._keys:
                raise ValueError(f"Key ID '{key_id}' not found")
            
            key = self._keys[key_id]
            fernet_key = self._derive_key(key.key.get_secret_value().encode('utf-8'))
            self._fernet_cache[key_id] = Fernet(fernet_key)
        
        return self._fernet_cache[key_id]

    def _derive_key(self, key: bytes) -> bytes:
        """Derive a proper Fernet key from the provided key using PBKDF2.
        
        Args:
            key: The input key as bytes
            
        Returns:
            A 32-byte key suitable for Fernet encryption
        """
        # Use a fixed salt for consistency (in production, you might want to store this)
        salt = b'openhands_salt_v1'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        derived_key = kdf.derive(key)
        return base64.urlsafe_b64encode(derived_key)

    def encrypt(self, text: str, key_id: str | None = None) -> Dict[str, str]:
        """Encrypt a text string.
        
        Args:
            text: The text to encrypt
            key_id: The key ID to use for encryption. If None, uses the newest key.
            
        Returns:
            A dictionary containing the encrypted text and key ID
            
        Raises:
            ValueError: If input is not a string or key_id is invalid
        """
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
        
        if key_id is None:
            key_id = self._default_key_id
        
        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")
        
        if not self._keys[key_id].use_for_encryption:
            raise ValueError(f"Key ID '{key_id}' is not marked for encryption")
        
        fernet = self._get_fernet(key_id)
        encrypted_bytes = fernet.encrypt(text.encode('utf-8'))
        encrypted_text = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        
        return {
            'encrypted_text': encrypted_text,
            'key_id': key_id
        }

    def decrypt(self, encrypted_data: Union[str, Dict[str, str]], key_id: str | None = None) -> str:
        """Decrypt an encrypted text string.
        
        Args:
            encrypted_data: Either a string (legacy format) or dict with encrypted_text and key_id
            key_id: The key ID to use for decryption. Required if encrypted_data is a string.
            
        Returns:
            The decrypted text as a string
            
        Raises:
            ValueError: If the encrypted data is invalid or cannot be decrypted
        """
        if isinstance(encrypted_data, str):
            # Legacy format - requires key_id parameter
            if key_id is None:
                raise ValueError("key_id is required when encrypted_data is a string")
            encrypted_text = encrypted_data
        elif isinstance(encrypted_data, dict):
            # New format with embedded key_id
            encrypted_text = encrypted_data.get('encrypted_text')
            key_id = encrypted_data.get('key_id')
            if not encrypted_text or not key_id:
                raise ValueError("encrypted_data dict must contain 'encrypted_text' and 'key_id'")
        else:
            raise ValueError("encrypted_data must be a string or dict")
        
        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")
        
        try:
            fernet = self._get_fernet(key_id)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt text: {str(e)}")

    def is_encrypted(self, data: Union[str, Dict[str, str]], key_id: str | None = None) -> bool:
        """Check if data appears to be encrypted by this service.
        
        Args:
            data: The data to check (string or dict format)
            key_id: The key ID to try (required if data is a string)
            
        Returns:
            True if the data appears to be encrypted, False otherwise
        """
        try:
            self.decrypt(data, key_id)
            return True
        except Exception:
            return False

    def create_jwt_token(
        self, 
        payload: Dict[str, Any], 
        key_id: str | None = None,
        expires_in: timedelta | None = None
    ) -> str:
        """Create a JWT token signed with the specified key.
        
        Args:
            payload: The JWT payload
            key_id: The key ID to use for signing. If None, uses the newest key.
            expires_in: Token expiration time. If None, defaults to 1 hour.
            
        Returns:
            The signed JWT token
            
        Raises:
            ValueError: If key_id is invalid
        """
        if key_id is None:
            key_id = self._default_key_id
        
        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")
        
        if not self._keys[key_id].use_for_encryption:
            raise ValueError(f"Key ID '{key_id}' is not marked for encryption")
        
        # Add standard JWT claims
        now = datetime.utcnow()
        if expires_in is None:
            expires_in = timedelta(hours=1)
        
        jwt_payload = {
            **payload,
            'iat': now,
            'exp': now + expires_in
        }
        
        # Use the raw key for JWT signing with key_id in header
        secret_key = self._keys[key_id].key.get_secret_value()
        
        return jwt.encode(
            jwt_payload, 
            secret_key, 
            algorithm='HS256',
            headers={'kid': key_id}
        )

    def verify_jwt_token(self, token: str, key_id: str | None = None) -> Dict[str, Any]:
        """Verify and decode a JWT token.
        
        Args:
            token: The JWT token to verify
            key_id: The key ID to use for verification. If None, extracts from token's kid header.
            
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
                key_id = unverified_header.get('kid')
                if not key_id:
                    raise ValueError("Token does not contain 'kid' header with key ID")
            except jwt.DecodeError:
                raise ValueError("Invalid JWT token format")
        
        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")
        
        # Use the raw key for JWT verification
        secret_key = self._keys[key_id].key.get_secret_value()
        
        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")

    def get_key_info(self, key_id: str) -> Dict[str, Any]:
        """Get information about a specific key.
        
        Args:
            key_id: The key ID
            
        Returns:
            Dictionary with key information (excluding the actual key value)
            
        Raises:
            ValueError: If key_id is not found
        """
        if key_id not in self._keys:
            raise ValueError(f"Key ID '{key_id}' not found")
        
        key = self._keys[key_id]
        return {
            'id': key.id,
            'use_for_encryption': key.use_for_encryption,
            'notes': key.notes,
            'created_at': key.created_at.isoformat()
        }

    def list_keys(self) -> list[Dict[str, Any]]:
        """List all available keys.
        
        Returns:
            List of key information dictionaries (excluding actual key values)
        """
        return [self.get_key_info(key_id) for key_id in self._keys.keys()]

    @property
    def default_key_id(self) -> str:
        """Get the default key ID used for encryption."""
        return self._default_key_id


# Global default encryption service instance
_default_encryption_service: EncryptionService | None = None


def get_default_encryption_service() -> EncryptionService:
    """Get the default encryption service instance using keys from config.
    
    Returns:
        The default EncryptionService instance
        
    Raises:
        ImportError: If the OpenHands config module is not available
    """
    if not _CONFIG_AVAILABLE:
        raise ImportError(
            "OpenHands config module is not available. "
            "This function requires the full OpenHands environment to be set up."
        )
    
    global _default_encryption_service
    if _default_encryption_service is None:
        _default_encryption_service = EncryptionService()
    return _default_encryption_service