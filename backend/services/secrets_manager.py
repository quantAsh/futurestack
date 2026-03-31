"""
Secrets Manager - Abstraction layer for secret storage.
Supports HashiCorp Vault, AWS Secrets Manager, and environment variables.
"""
import os
from typing import Optional, Dict, Any
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SecretsBackend(str, Enum):
    ENV = "env"
    VAULT = "vault"
    AWS = "aws"


# Configuration
SECRETS_BACKEND = os.getenv("SECRETS_BACKEND", "env")
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")
VAULT_PATH = os.getenv("VAULT_PATH", "secret/data/nomadnest")
AWS_SECRETS_PREFIX = os.getenv("AWS_SECRETS_PREFIX", "nomadnest")


class SecretsManager:
    """Unified interface for secret retrieval."""
    
    def __init__(self, backend: str = None):
        self.backend = SecretsBackend(backend or SECRETS_BACKEND)
        self._cache: Dict[str, str] = {}
        self._vault_client = None
        self._aws_client = None
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value.
        
        Args:
            key: Secret key name
            default: Default value if not found
        
        Returns:
            Secret value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        value = None
        
        if self.backend == SecretsBackend.ENV:
            value = self._get_from_env(key)
        elif self.backend == SecretsBackend.VAULT:
            value = self._get_from_vault(key)
        elif self.backend == SecretsBackend.AWS:
            value = self._get_from_aws(key)
        
        if value is not None:
            self._cache[key] = value
            return value
        
        return default
    
    def _get_from_env(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        return os.getenv(key) or os.getenv(key.upper())
    
    def _get_from_vault(self, key: str) -> Optional[str]:
        """Get secret from HashiCorp Vault."""
        if not VAULT_TOKEN:
            logger.warning("Vault token not configured, falling back to env")
            return self._get_from_env(key)
        
        try:
            if self._vault_client is None:
                import hvac
                self._vault_client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
            
            response = self._vault_client.secrets.kv.v2.read_secret_version(
                path=f"nomadnest/{key}",
                mount_point="secret",
            )
            return response["data"]["data"].get("value")
        
        except ImportError:
            logger.warning("hvac package not installed, falling back to env")
            return self._get_from_env(key)
        except Exception as e:
            logger.error(f"Vault error: {e}, falling back to env")
            return self._get_from_env(key)
    
    def _get_from_aws(self, key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager."""
        try:
            if self._aws_client is None:
                import boto3
                self._aws_client = boto3.client("secretsmanager")
            
            secret_name = f"{AWS_SECRETS_PREFIX}/{key}"
            response = self._aws_client.get_secret_value(SecretId=secret_name)
            return response.get("SecretString")
        
        except ImportError:
            logger.warning("boto3 package not installed, falling back to env")
            return self._get_from_env(key)
        except Exception as e:
            logger.error(f"AWS Secrets Manager error: {e}, falling back to env")
            return self._get_from_env(key)
    
    def set(self, key: str, value: str) -> bool:
        """
        Set a secret value (only supported for Vault backend).
        
        Args:
            key: Secret key name
            value: Secret value
        
        Returns:
            Success status
        """
        if self.backend != SecretsBackend.VAULT:
            logger.warning("Secret setting only supported for Vault backend")
            return False
        
        try:
            if self._vault_client is None:
                import hvac
                self._vault_client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)
            
            self._vault_client.secrets.kv.v2.create_or_update_secret(
                path=f"nomadnest/{key}",
                secret={"value": value},
                mount_point="secret",
            )
            self._cache[key] = value
            return True
        
        except Exception as e:
            logger.error(f"Failed to set secret: {e}")
            return False
    
    def clear_cache(self):
        """Clear the secrets cache."""
        self._cache = {}
    
    def get_required_secrets(self) -> Dict[str, bool]:
        """Check which required secrets are configured."""
        required = [
            "DATABASE_URL",
            "OPENAI_API_KEY",
            "STRIPE_API_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "JWT_SECRET_KEY",
        ]
        
        return {key: self.get(key) is not None for key in required}


# Singleton instance
secrets = SecretsManager()


# Convenience functions
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret value."""
    return secrets.get(key, default)


def get_database_url() -> str:
    """Get database connection URL."""
    return get_secret("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nomadnest")


def get_jwt_secret() -> str:
    """Get JWT signing secret."""
    return get_secret("JWT_SECRET_KEY", "dev-secret-change-in-production")


def get_stripe_key() -> Optional[str]:
    """Get Stripe API key."""
    return get_secret("STRIPE_API_KEY")


def get_openai_key() -> Optional[str]:
    """Get OpenAI API key."""
    return get_secret("OPENAI_API_KEY")
