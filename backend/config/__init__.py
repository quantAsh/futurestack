# Backend config module
# Re-export settings from the original config for backwards compatibility
import sys
import os

# Import original settings from config.py (renamed)
from backend.config.settings import settings, Settings

# Export GCP utilities
from backend.config.secrets import (
    get_secret,
    get_secrets_batch,
    get_database_url,
    get_redis_url,
    is_gcp_environment,
)
from backend.config.cloud_logging import setup_cloud_logging

__all__ = [
    "settings",
    "Settings",
    "get_secret",
    "get_secrets_batch", 
    "get_database_url",
    "get_redis_url",
    "is_gcp_environment",
    "setup_cloud_logging",
]
