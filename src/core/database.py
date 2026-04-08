"""
Database setup for billing service.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from .config import settings
from .compat import CompatUUID

# Handle SQLite vs PostgreSQL
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class BillingCache:
    """
    Lightweight in-memory cache for billing calculations.
    
    Used for:
    - usage aggregation
    - invoice previews
    - quota checks
    - subscription status lookups
    """
    
    _cache = {}
    
    @classmethod
    def get(cls, key: str):
        """Get value from cache."""
        return cls._cache.get(key)
    
    @classmethod
    def set(cls, key: str, value, ttl: int = 3600):
        """Set value in cache with TTL (ignored for now, placeholder)."""
        cls._cache[key] = value
    
    @classmethod
    def delete(cls, key: str):
        """Delete key from cache."""
        if key in cls._cache:
            del cls._cache[key]
    
    @classmethod
    def clear(cls):
        """Clear entire cache."""
        cls._cache.clear()
    
    @classmethod
    def exists(cls, key: str) -> bool:
        """Check if key exists in cache."""
        return key in cls._cache


def get_db():
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


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified")

class BillingCache:
    """
    Temporary in-memory cache until Redis is configured.
    Used for usage metering aggregation.
    """

    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value

    def increment(self, key, amount=1):
        self.cache[key] = self.cache.get(key, 0) + amount
        return self.cache[key]

    def reset(self, key):
        if key in self.cache:
            del self.cache[key]