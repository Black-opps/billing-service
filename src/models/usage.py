"""
Usage metering models.
"""
from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, Enum, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..core.database import Base


class MetricType(str, enum.Enum):
    """Types of usage metrics."""
    COUNT = "count"  # Number of occurrences
    DURATION = "duration"  # Time in seconds
    VOLUME = "volume"  # Data volume in MB
    RATE = "rate"  # Per second/minute


class UsageRecord(Base):
    """Individual usage record."""
    
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    
    # Metric
    metric_name = Column(String(100), nullable=False, index=True)  # 'transactions_parsed', 'api_calls', 'storage_mb'
    metric_type = Column(Enum(MetricType), default=MetricType.COUNT)
    quantity = Column(BigInteger, nullable=False, default=0)
    
    # Time
    timestamp = Column(DateTime, nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)  # '2026-03' for monthly aggregation
    
    # Source
    service = Column(String(50), nullable=False)  # 'parser', 'categorizer', 'analyzer', 'api'
    
    # Metadata
    metadata = Column(JSON, default=dict)
    idempotency_key = Column(String(255), unique=True, nullable=True)  # For deduplication
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_usage_tenant_metric_period', 'tenant_id', 'metric_name', 'period'),
    )
    
    def __repr__(self):
        return f"<Usage {self.metric_name}: {self.quantity} at {self.timestamp}>"


class UsageAlert(Base):
    """Usage threshold alerts."""
    
    __tablename__ = "usage_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"))
    
    # Alert details
    metric_name = Column(String(100), nullable=False)
    threshold = Column(Float, nullable=False)  # 0.8 for 80%
    current_usage = Column(BigInteger, nullable=False)
    limit = Column(BigInteger, nullable=False)
    
    # Status
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UsageAlert {self.metric_name}: {self.current_usage}/{self.limit}>"


class UsageAggregate(Base):
    """Pre-aggregated usage for faster queries."""
    
    __tablename__ = "usage_aggregates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"))
    
    # Aggregation
    metric_name = Column(String(100), nullable=False)
    period = Column(String(7), nullable=False)  # '2026-03'
    total = Column(BigInteger, nullable=False, default=0)
    
    # Breakdown by service
    by_service = Column(JSON, default=dict)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'metric_name', 'period', name='uq_usage_aggregate'),
    )