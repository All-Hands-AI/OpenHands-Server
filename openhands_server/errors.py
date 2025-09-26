class OpenHandsError(Exception):
    pass


class AuthError(OpenHandsError):
    """Execution in authentication"""


class PermissionsError(OpenHandsError):
    """Execution in permissions"""
