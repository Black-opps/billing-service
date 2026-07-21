# billing-service/src/models/usage.py - Complete Usage Models

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from src.core.database import Base


class Usage(Base):
    """Current usage for a tenant in the current billing period"""

    __tablename__ = "usage_tracking"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    billing_period = Column(String, nullable=False)  # "2024-07"

    # Core metrics
    transactions_processed = Column(Integer, default=0)
    statements_uploaded = Column(Integer, default=0)
    exports_generated = Column(Integer, default=0)
    ai_insights_generated = Column(Integer, default=0)

    # Historical tracking
    historical_months_imported = Column(Integer, default=0)
    earliest_transaction_date = Column(DateTime, nullable=True)
    latest_transaction_date = Column(DateTime, nullable=True)

    # Overage
    overage_transactions = Column(Integer, default=0)
    overage_charges = Column(Float, default=0.0)
    overage_paid = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_usage_tenant_period", "tenant_id", "billing_period", unique=True),
        Index(
            "idx_usage_tenant_period_transactions",
            "tenant_id",
            "billing_period",
            "transactions_processed",
        ),
    )


class UsageEvent(Base):
    """Audit trail for all usage events"""

    __tablename__ = "usage_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    event_type = Column(String)  # "upload", "export", "ai_insight"
    transaction_count = Column(Integer, default=0)
    upload_id = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    statement_start = Column(DateTime, nullable=True)
    statement_end = Column(DateTime, nullable=True)
    is_historical = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_usage_events_tenant_processed", "tenant_id", "processed"),
        Index("idx_usage_events_created", "created_at"),
    )


class OverageLog(Base):
    """Track all overages for finance and auditing"""

    __tablename__ = "overage_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    billing_period = Column(String, nullable=False)
    threshold = Column(Integer, nullable=False)
    actual = Column(Integer, nullable=False)
    overage_amount = Column(Integer, nullable=False)
    charge = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, charged, paid, waived
    invoice_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_overage_tenant_period", "tenant_id", "billing_period"),
        Index("idx_overage_status", "status"),
    )


class HistoricalBackfillRequest(Base):
    """Track historical backfill requests for monetization"""

    __tablename__ = "historical_backfill_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    months_requested = Column(Integer, nullable=False)
    months_processed = Column(Integer, default=0)
    status = Column(
        String, default="pending"
    )  # pending, approved, processing, completed, failed
    price = Column(Float, nullable=False)
    payment_id = Column(String, nullable=True)
    invoice_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_backfill_tenant_status", "tenant_id", "status"),)
