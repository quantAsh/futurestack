"""
Secrets Management Service - Unified interface for secrets retrieval.

Supports:
- Environment variables (development)
- AWS Secrets Manager (production)
- HashiCorp Vault (optional)
"""
import os
import json
import structlog
from typing import Optional, Dict, Any
from functools import lru_cache

logger = structlog.get_logger("nomadnest.secrets")


class SecretsProvider:
    """Base class for secrets providers."""

    def get_secret(self, key: str) -> Optional[str]:
        raise NotImplementedError


class EnvironmentProvider(SecretsProvider):
    """Get secrets from environment variables (development)."""

    def get_secret(self, key: str) -> Optional[str]:
        return os.environ.get(key)


class AWSSecretsManagerProvider(SecretsProvider):
    """Get secrets from AWS Secrets Manager (production)."""

    def __init__(self, secret_name: str, region: str = "us-east-1"):
        self.secret_name = secret_name
        self.region = region
        self._client = None
        self._cache: Dict[str, str] = {}
        self._loaded = False

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("secretsmanager", region_name=self.region)
            except ImportError:
                raise ImportError("boto3 required for AWS Secrets Manager. Install with: pip install boto3")
        return self._client

    def _load_secrets(self):
        if self._loaded:
            return

        try:
            client = self._get_client()
            response = client.get_secret_value(SecretId=self.secret_name)
            secret_string = response.get("SecretString", "{}")
            self._cache = json.loads(secret_string)
            self._loaded = True
        except Exception as e:
            logger.warning("aws_secrets_load_failed", error=str(e))
            self._cache = {}
            self._loaded = True

    def get_secret(self, key: str) -> Optional[str]:
        self._load_secrets()
        return self._cache.get(key)


class VaultProvider(SecretsProvider):
    """Get secrets from HashiCorp Vault (optional)."""

    def __init__(self, vault_addr: str, vault_token: str, mount_path: str = "secret"):
        self.vault_addr = vault_addr
        self.vault_token = vault_token
        self.mount_path = mount_path
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            except ImportError:
                raise ImportError("hvac required for Vault. Install with: pip install hvac")
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        try:
            client = self._get_client()
            # Assume KV v2 secrets engine
            response = client.secrets.kv.v2.read_secret_version(
                path="nomadnest",
                mount_point=self.mount_path,
            )
            return response["data"]["data"].get(key)
        except Exception as e:
            logger.warning("vault_secret_failed", key=key, error=str(e))
            return None


class GCPSecretManagerProvider(SecretsProvider):
    """Get secrets from Google Cloud Secret Manager (GCP production)."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError:
                raise ImportError(
                    "google-cloud-secret-manager required for GCP. "
                    "Install with: pip install google-cloud-secret-manager"
                )
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        try:
            client = self._get_client()
            # Format: nomadnest-secret-key -> SECRET_KEY
            secret_name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            # Try with transformed name (SECRET_KEY -> nomadnest-secret-key)
            try:
                normalized = key.lower().replace("_", "-")
                secret_name = f"projects/{self.project_id}/secrets/nomadnest-{normalized}/versions/latest"
                response = client.access_secret_version(request={"name": secret_name})
                return response.payload.data.decode("UTF-8")
            except Exception:
                pass
            return None


class SecretsService:
    """
    Unified secrets management with fallback chain.
    
    Priority:
    1. AWS Secrets Manager (if configured)
    2. HashiCorp Vault (if configured)
    3. Environment variables (always available)
    """

    def __init__(self):
        self._providers: list[SecretsProvider] = []
        self._setup_providers()

    def _setup_providers(self):
        """Configure providers based on environment."""
        environment = os.environ.get("ENVIRONMENT", "development")

        # AWS Secrets Manager (production)
        aws_secret_name = os.environ.get("AWS_SECRET_NAME")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        if aws_secret_name and environment == "production":
            try:
                self._providers.append(AWSSecretsManagerProvider(aws_secret_name, aws_region))
                logger.info("secrets_provider_configured", provider="aws")
            except Exception as e:
                logger.warning("secrets_provider_unavailable", provider="aws", error=str(e))

        # HashiCorp Vault (optional)
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if vault_addr and vault_token:
            try:
                self._providers.append(VaultProvider(vault_addr, vault_token))
                logger.info("secrets_provider_configured", provider="vault")
            except Exception as e:
                logger.warning("secrets_provider_unavailable", provider="vault", error=str(e))

        # GCP Secret Manager (GCP production)
        gcp_project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if gcp_project and environment == "production":
            try:
                self._providers.append(GCPSecretManagerProvider(gcp_project))
                logger.info("secrets_provider_configured", provider="gcp")
            except Exception as e:
                logger.warning("secrets_provider_unavailable", provider="gcp", error=str(e))

        # Environment variables (always available as fallback)
        self._providers.append(EnvironmentProvider())

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value using the configured providers.
        
        Args:
            key: Secret key name
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        for provider in self._providers:
            value = provider.get_secret(key)
            if value is not None:
                return value
        return default

    def get_secrets(self, keys: list[str]) -> Dict[str, Optional[str]]:
        """Get multiple secrets at once."""
        return {key: self.get_secret(key) for key in keys}


# Singleton instance
@lru_cache(maxsize=1)
def get_secrets_service() -> SecretsService:
    """Get the singleton secrets service instance."""
    return SecretsService()


# Convenience function
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret value."""
    return get_secrets_service().get_secret(key, default)
