import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security-enhancing HTTP headers to all responses.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable Browser XSS filter (mostly for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict-Transport-Security (HSTS) - only for HTTPS
        # 31536000 seconds = 1 year
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy (CSP)
        # Note: 'unsafe-inline' is kept for Vite dev mode compatibility.
        # For production, consider nonce-based CSP via a per-request nonce header.
        csp_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "img-src 'self' data: https://images.unsplash.com https://*.fastly.net",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://api.openai.com https://api.stripe.com https://generativelanguage.googleapis.com https://api.elevenlabs.io https://api.heygen.com",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)
        
        return response
