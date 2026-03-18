"""
Configuration management for billing service.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List, Dict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_VERSION: str = "v1"
    API_PORT: int = 8005
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    REDIS_TTL: int = 3600  # 1 hour
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = Field("localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    KAFKA_USAGE_TOPIC: str = "usage-events"
    KAFKA_BILLING_TOPIC: str = "billing-events"
    KAFKA_PAYMENT_TOPIC: str = "payment-events"
    
    # Billing Settings
    CURRENCY: str = "KES"
    TAX_RATE: float = 0.16  # 16% VAT
    BILLING_CYCLE_DAY: int = 1  # 1st of month
    GRACE_PERIOD_DAYS: int = 7
    INVOICE_DUE_DAYS: int = 14
    
    # Payment Processing
    PAYMENT_PROVIDER: str = "mpesa"  # mpesa, stripe, etc.
    MPESA_SHORTCODE: str = Field("174379", env="MPESA_SHORTCODE")
    MPESA_CONSUMER_KEY: Optional[str] = Field(None, env="MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET: Optional[str] = Field(None, env="MPESA_CONSUMER_SECRET")
    MPESA_PASSKEY: Optional[str] = Field(None, env="MPESA_PASSKEY")
    MPESA_ENV: str = "sandbox"
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "billing@mpesa-saas.com"
    
    # Pricing Plans (loaded from DB, but defaults here)
    DEFAULT_PLANS: Dict = {
        "free": {
            "name": "Free",
            "price": 0,
            "currency": "KES",
            "interval": "month",
            "features": ["Basic Analytics", "100 transactions/month"],
            "limits": {"transactions": 100, "users": 1, "reports": 5}
        },
        "starter": {
            "name": "Starter",
            "price": 2900,  # KES 29
            "currency": "KES",
            "interval": "month",
            "features": ["Advanced Analytics", "5,000 transactions/month", "3 users"],
            "limits": {"transactions": 5000, "users": 3, "reports": 50}
        },
        "professional": {
            "name": "Professional",
            "price": 9900,  # KES 99
            "currency": "KES",
            "interval": "month",
            "features": ["Real-time Analytics", "50,000 transactions/month", "10 users", "API Access"],
            "limits": {"transactions": 50000, "users": 10, "reports": 200}
        },
        "enterprise": {
            "name": "Enterprise",
            "price": 0,  # Custom pricing
            "currency": "KES",
            "interval": "month",
            "features": ["Unlimited transactions", "Custom retention", "Unlimited users", "SLA"],
            "limits": {"transactions": 999999, "users": 999, "reports": 9999}
        }
    }
    
    # Alert thresholds (% of limit)
    USAGE_ALERT_THRESHOLDS: List[float] = [0.5, 0.8, 0.9, 1.0]
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings."""
    return Settings()


settings = get_settings()