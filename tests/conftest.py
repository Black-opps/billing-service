# billing-service/tests/conftest.py
"""
Pytest configuration for billing service tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.core.database import Base, get_db
from src.main import app
from src.models.plan import Plan
from src.models.plan_data import DEFAULT_PLANS
from src.models.subscription import Subscription

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_billing.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """Clean all tables after each test."""
    yield
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM subscriptions"))
        conn.execute(text("DELETE FROM plans"))
        conn.commit()


@pytest.fixture
def db_session():
    """Get a database session for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def override_get_db():
    """Override the get_db dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Create a test client."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)


@pytest.fixture
def test_token():
    """Return a test JWT token."""
    return "test_token_123"


@pytest.fixture
def test_tenant_id():
    """Return a test tenant ID."""
    return "3ba93007-ce03-459e-a449-c853ca60d51b"


@pytest.fixture
def default_plans(db_session):
    """Seed default plans in the database."""
    for plan_data in DEFAULT_PLANS:
        plan = Plan(**plan_data)
        db_session.add(plan)
    db_session.commit()
    return db_session.query(Plan).all()


@pytest.fixture
def free_plan(default_plans):
    """Get the free plan."""
    return next((p for p in default_plans if p.plan_id == "free"), None)


@pytest.fixture
def active_subscription(db_session, test_tenant_id, free_plan):
    """Create an active subscription for testing."""
    from datetime import datetime, timedelta

    subscription = Subscription(
        tenant_id=test_tenant_id,
        plan_id=free_plan.id,
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        auto_renew=True,
        usage={"transactions": 0, "uploads": 0},
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription
