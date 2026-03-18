"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import redis
import json
from contextlib import contextmanager
import logging

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5
)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class BillingCache:
    """Redis cache for billing data."""
    
    @staticmethod
    def get_subscription(tenant_id: str):
        """Get subscription from cache."""
        data = redis_client.get(f"subscription:{tenant_id}")
        return json.loads(data) if data else None
    
    @staticmethod
    def set_subscription(tenant_id: str, sub_data: dict):
        """Set subscription in cache."""
        redis_client.setex(
            f"subscription:{tenant_id}",
            settings.REDIS_TTL,
            json.dumps(sub_data, default=str)
        )
    
    @staticmethod
    def invalidate_subscription(tenant_id: str):
        """Invalidate subscription cache."""
        redis_client.delete(f"subscription:{tenant_id}")
    
    @staticmethod
    def get_usage(tenant_id: str, metric: str, period: str):
        """Get usage from cache."""
        data = redis_client.get(f"usage:{tenant_id}:{metric}:{period}")
        return json.loads(data) if data else None
    
    @staticmethod
    def set_usage(tenant_id: str, metric: str, period: str, usage_data: dict):
        """Set usage in cache."""
        redis_client.setex(
            f"usage:{tenant_id}:{metric}:{period}",
            3600,  # 1 hour cache for usage
            json.dumps(usage_data, default=str)
        )