from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class NomadNestError(Exception):
    """Base class for all NomadNest exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(NomadNestError):
    """Exception raised for validation errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class AuthenticationError(NomadNestError):
    """Exception raised for authentication or authorization failures."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(NomadNestError):
    """Exception raised for permission denied errors."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="FORBIDDEN_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ResourceNotFoundError(NomadNestError):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier {identifier} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class DependencyError(NomadNestError):
    """Exception raised when an external dependency (AI, Payment) fails."""

    def __init__(
        self, service: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"External service '{service}' error: {message}",
            code="DEPENDENCY_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service, **(details or {})},
        )


class RateLimitError(NomadNestError):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
