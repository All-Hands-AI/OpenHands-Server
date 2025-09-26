# Utils package

# Re-export JWT service from services package for backward compatibility
from openhands_server.services import JWTService, get_default_jwt_service

# Maintain backward compatibility with old names
EncryptionService = JWTService
get_default_encryption_service = get_default_jwt_service

__all__ = ["JWTService", "get_default_jwt_service", "EncryptionService", "get_default_encryption_service"]
