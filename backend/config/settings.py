import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str | None:
    """Return '.env' only if the file exists and is readable."""
    if os.environ.get("TESTING"):
        return None  # skip .env during tests
    try:
        p = Path(".env")
        if p.is_file():
            return ".env"
    except (PermissionError, OSError):
        pass
    return None


class Settings(BaseSettings):
    PROJECT_NAME: str = "NomadNest AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # DATABASE
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "nomadnest"
    DATABASE_URL: str = ""

    # REDIS
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_URL: str = ""

    # SECURITY
    SECRET_KEY: str = ""  # MUST be set via environment variable
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"  # development, staging, production

    # OAUTH
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:5173"
    # Comma-separated list of allowed CORS origins for production
    # e.g. "https://app.nomadnest.ai,https://www.nomadnest.ai"
    ALLOWED_ORIGINS: str = ""

    # AI PROVIDERS
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # STRIPE — Subscription billing
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    # Traveler plans
    STRIPE_NOMAD_PRICE_ID: str | None = None      # $9/mo
    STRIPE_PRO_PRICE_ID: str | None = None         # $29/mo
    STRIPE_ANNUAL_PRICE_ID: str | None = None      # $199/yr
    STRIPE_UNLIMITED_PRICE_ID: str | None = None   # legacy alias
    # Host plans
    STRIPE_HOST_PRO_PRICE_ID: str | None = None    # $19/mo
    STRIPE_HOST_MANAGER_PRICE_ID: str | None = None  # $49/mo

    # PUSH NOTIFICATIONS (Phase 14)
    VAPID_PUBLIC_KEY: str | None = None
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_CLAIM_EMAIL: str = "mailto:support@nomadnest.ai"

    # PREMIUM MEDIA (Voice & Avatar)
    ELEVENLABS_API_KEY: str | None = None
    HEYGEN_API_KEY: str | None = None

    # MONITORING & ALERTING
    PAGERDUTY_ROUTING_KEY: str | None = None
    OPSGENIE_API_KEY: str | None = None
    SLACK_WEBHOOK_URL: str | None = None

    # OBSERVABILITY
    SENTRY_DSN: str | None = None

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=_resolve_env_file(), extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Build DATABASE_URL if not explicitly set
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

        # Build REDIS_URL if not explicitly set
        if not self.REDIS_URL:
            self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"
            if self.REDIS_PASSWORD:
                self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"

        # SECRET_KEY validation
        if not self.SECRET_KEY:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "SECRET_KEY must be set in production! "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
            else:
                # Auto-generate for development convenience
                import secrets

                self.SECRET_KEY = secrets.token_urlsafe(32)
                import structlog
                _logger = structlog.get_logger("nomadnest.settings")
                _logger.warning(
                    "auto_generated_secret_key",
                    environment=self.ENVIRONMENT,
                )


settings = Settings()
