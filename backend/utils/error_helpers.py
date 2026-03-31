"""
Error Utilities - Helper functions for consistent error responses.
Use these instead of raising raw HTTPException for standardized error format.
"""
from backend.errors import (
    NomadNestError,
    ValidationError,
    AuthenticationError,
    ForbiddenError,
    ResourceNotFoundError,
    DependencyError,
    RateLimitError,
)


def not_found(resource: str, identifier: str):
    """
    Raise a standard 404 Not Found error.
    
    Usage:
        from backend.utils.error_helpers import not_found
        
        if not listing:
            raise not_found("Listing", listing_id)
    """
    raise ResourceNotFoundError(resource=resource, identifier=identifier)


def forbidden(message: str = "Permission denied"):
    """Raise a standard 403 Forbidden error."""
    raise ForbiddenError(message=message)


def bad_request(message: str, details: dict = None):
    """Raise a standard 400 Validation error."""
    raise ValidationError(message=message, details=details)


def unauthorized(message: str = "Authentication required"):
    """Raise a standard 401 Unauthorized error."""
    raise AuthenticationError(message=message)


def service_unavailable(service: str, message: str):
    """Raise a standard 502 Bad Gateway for external service failures."""
    raise DependencyError(service=service, message=message)


def rate_limited(message: str = "Too many requests. Please try again later."):
    """Raise a standard 429 Rate Limit error."""
    raise RateLimitError(message=message)


# Mapping of common scenarios to error codes
ERROR_CODES = {
    "NOT_FOUND": "The requested resource was not found",
    "VALIDATION_ERROR": "The request contains invalid data",
    "AUTHENTICATION_ERROR": "Authentication is required or failed",
    "FORBIDDEN_ERROR": "You do not have permission to perform this action",
    "RATE_LIMIT_ERROR": "Request rate limit exceeded",
    "DEPENDENCY_ERROR": "An external service is unavailable",
    "INTERNAL_ERROR": "An unexpected error occurred",
}
