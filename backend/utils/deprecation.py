"""
API Deprecation Utilities - Mark endpoints as deprecated with proper headers.
"""
import warnings
import functools
from datetime import date
from typing import Optional, Callable
from fastapi import Response


def deprecated(
    reason: str,
    sunset_date: Optional[date] = None,
    replacement: Optional[str] = None,
):
    """
    Decorator to mark an endpoint as deprecated.
    Adds Deprecation and Sunset headers per RFC 8594.
    
    Usage:
        @router.get("/old-endpoint")
        @deprecated(
            reason="Use /v2/new-endpoint instead",
            sunset_date=date(2025, 6, 1),
            replacement="/api/v2/new-endpoint"
        )
        async def old_endpoint():
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, response: Response = None, **kwargs):
            # Find response object in kwargs or args
            resp = response
            if resp is None:
                for arg in args:
                    if isinstance(arg, Response):
                        resp = arg
                        break
            
            # Build deprecation message
            msg = f"DEPRECATED: {reason}"
            if replacement:
                msg += f" → {replacement}"
            
            # Add headers
            if resp:
                # RFC 8594 Deprecation header
                resp.headers["Deprecation"] = "true"
                resp.headers["X-Deprecation-Notice"] = msg
                
                if sunset_date:
                    resp.headers["Sunset"] = sunset_date.isoformat()
                
                if replacement:
                    resp.headers["Link"] = f'<{replacement}>; rel="successor-version"'
            
            # Issue Python warning (logged)
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            
            return await func(*args, **kwargs)
        
        # Store deprecation info for OpenAPI
        wrapper.__deprecated__ = True
        wrapper.__deprecation_reason__ = reason
        wrapper.__sunset_date__ = sunset_date
        wrapper.__replacement__ = replacement
        
        return wrapper
    return decorator


def deprecated_sync(
    reason: str,
    sunset_date: Optional[date] = None,
    replacement: Optional[str] = None,
):
    """
    Synchronous version of deprecated decorator.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, response: Response = None, **kwargs):
            resp = response
            if resp is None:
                for arg in args:
                    if isinstance(arg, Response):
                        resp = arg
                        break
            
            msg = f"DEPRECATED: {reason}"
            if replacement:
                msg += f" → {replacement}"
            
            if resp:
                resp.headers["Deprecation"] = "true"
                resp.headers["X-Deprecation-Notice"] = msg
                
                if sunset_date:
                    resp.headers["Sunset"] = sunset_date.isoformat()
                
                if replacement:
                    resp.headers["Link"] = f'<{replacement}>; rel="successor-version"'
            
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            
            return func(*args, **kwargs)
        
        wrapper.__deprecated__ = True
        wrapper.__deprecation_reason__ = reason
        wrapper.__sunset_date__ = sunset_date
        wrapper.__replacement__ = replacement
        
        return wrapper
    return decorator


# ============================================================================
# Parameter Deprecation
# ============================================================================

def deprecated_param(
    param_name: str,
    reason: str,
    replacement: Optional[str] = None,
):
    """
    Issue a warning when a deprecated parameter is used.
    
    Usage:
        def endpoint(old_param: str = None, new_param: str = None):
            if old_param:
                deprecated_param("old_param", "Use new_param instead", "new_param")
                new_param = old_param
            ...
    """
    msg = f"Parameter '{param_name}' is deprecated: {reason}"
    if replacement:
        msg += f" → Use '{replacement}'"
    
    warnings.warn(msg, DeprecationWarning, stacklevel=2)


# ============================================================================
# Schema Field Deprecation (for Pydantic models)
# ============================================================================

def DeprecatedField(
    default=None,
    reason: str = "This field is deprecated",
    replacement: Optional[str] = None,
    **kwargs
):
    """
    Create a deprecated Pydantic field with description.
    
    Usage:
        class MySchema(BaseModel):
            old_field: str = DeprecatedField(
                None,
                reason="Use new_field instead",
                replacement="new_field"
            )
    """
    from pydantic import Field
    
    description = f"⚠️ DEPRECATED: {reason}"
    if replacement:
        description += f" → Use '{replacement}'"
    
    # Add to any existing description
    if "description" in kwargs:
        description = f"{kwargs.pop('description')}\n\n{description}"
    
    return Field(
        default=default,
        description=description,
        deprecated=True,
        **kwargs
    )
