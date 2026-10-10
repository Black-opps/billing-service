# billing-service/src/core/config.py
"""
Configuration management for billing service.
"""

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    API_VERSION: str = "v1"
    API_PORT: int = 8005
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite:///./billing.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    REDIS_TTL: int = 3600

    # Service Dependencies
    # Use port 8001 directly (auth service), not 9000 (gateway)
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    KAFKA_BOOTSTRAP_SERVERS: Optional[str] = Field(None, env="KAFKA_BOOTSTRAP_SERVERS")
    KAFKA_USAGE_TOPIC: str = "usage-events"
    KAFKA_BILLING_TOPIC: str = "billing-events"
    KAFKA_PAYMENT_TOPIC: str = "payment-events"

    # Billing Settings
    DEFAULT_CURRENCY: str = "KES"
    TAX_RATE: float = 0.16  # 16% VAT
    GRACE_PERIOD_DAYS: int = 7
    INVOICE_DUE_DAYS: int = 14
    BILLING_CYCLE_DAY: int = 1

    # M-PESA Configuration
    MPESA_SHORTCODE: str = "174379"
    MPESA_CONSUMER_KEY: Optional[str] = None
    MPESA_CONSUMER_SECRET: Optional[str] = None
    MPESA_PASSKEY: Optional[str] = None
    MPESA_ENV: str = "sandbox"

    # Email
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = "apikey"
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "billing@mpesa-saas.com"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Sentry
    SENTRY_DSN: Optional[str] = None

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8003"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from environment variable."""
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )


settings = Settings()
