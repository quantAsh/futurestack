"""
GCP Secret Manager Integration.
Fetches secrets from GCP Secret Manager in production,
falls back to environment variables for local development.
"""
import os
from functools import lru_cache
from typing import Optional
import structlog

logger = structlog.get_logger("nomadnest.secrets")

# GCP Project ID (set via environment)
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")


def is_gcp_environment() -> bool:
    """Check if running in GCP environment."""
    return bool(GCP_PROJECT_ID) and os.getenv("ENVIRONMENT", "development") == "production"


@lru_cache(maxsize=100)
def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Fetch a secret from GCP Secret Manager or environment.
    
    Priority:
    1. Environment variable (for local dev)
    2. GCP Secret Manager (for production)
    3. Default value
    """
    # First, check environment variable
    env_value = os.getenv(secret_name)
    if env_value:
        return env_value
    
    # If not in GCP, return default
    if not is_gcp_environment():
        return default
    
    # Fetch from GCP Secret Manager
    try:
        from google.cloud import secretmanager
        
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
        
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8")
        
        logger.info("secret_fetched", secret=secret_name)
        return secret_value
        
    except ImportError:
        logger.warning("google_cloud_secretmanager_not_installed")
        return default
    except Exception as e:
        logger.warning("secret_fetch_error", secret=secret_name, error=str(e))
        return default


def get_secrets_batch(secret_names: list[str]) -> dict[str, Optional[str]]:
    """Fetch multiple secrets at once."""
    return {name: get_secret(name) for name in secret_names}


# Convenience functions for common secrets
def get_database_url() -> str:
    """Get database URL from secret or build from components."""
    # Try explicit DATABASE_URL first
    db_url = get_secret("DATABASE_URL")
    if db_url:
        return db_url
    
    # Build from components
    user = get_secret("POSTGRES_USER", "postgres")
    password = get_secret("POSTGRES_PASSWORD", "postgres")
    host = get_secret("POSTGRES_SERVER", "localhost")
    port = get_secret("POSTGRES_PORT", "5432")
    db = get_secret("POSTGRES_DB", "nomadnest")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_redis_url() -> str:
    """Get Redis URL from secret or build from components."""
    redis_url = get_secret("REDIS_URL")
    if redis_url:
        return redis_url
    
    host = get_secret("REDIS_HOST", "localhost")
    port = get_secret("REDIS_PORT", "6379")
    password = get_secret("REDIS_PASSWORD")
    
    if password:
        return f"redis://:{password}@{host}:{port}/0"
    return f"redis://{host}:{port}/0"


# Production secret names (must exist in GCP Secret Manager)
REQUIRED_PRODUCTION_SECRETS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "GEMINI_API_KEY",
]

OPTIONAL_SECRETS = [
    "OPENAI_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "STRIPE_API_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "SENDGRID_API_KEY",
    "SENTRY_DSN",
]
