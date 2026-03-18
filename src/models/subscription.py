"""
Subscription models.
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta
import enum

from ..core.database import Base


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class Subscription(Base):
    """Subscription model."""
    
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    
    # Status
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIALING, nullable=False)
    
    # Billing
    billing_cycle = Column(Enum(BillingInterval), default=BillingInterval.MONTHLY)
    currency = Column(String(3), default="KES")
    
    # Pricing (snapshot at subscription time)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    
    # Dates
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime, nullable=True)
    
    # Payment
    payment_method_id = Column(UUID(as_uuid=True), nullable=True)
    auto_renew = Column(Boolean, default=True)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    plan = relationship("Plan")
    invoices = relationship("Invoice", back_populates="subscription")
    
    def __repr__(self):
        return f"<Subscription {self.id}: {self.status.value}>"
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status == SubscriptionStatus.ACTIVE
    
    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial."""
        return self.status == SubscriptionStatus.TRIALING
    
    @property
    def days_until_renewal(self) -> int:
        """Get days until renewal."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def days_into_period(self) -> int:
        """Get days into current period."""
        if not self.current_period_start:
            return 0
        delta = datetime.utcnow() - self.current_period_start
        return max(0, delta.days)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "plan": self.plan.to_dict() if self.plan else None,
            "status": self.status.value,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "auto_renew": self.auto_renew,
            "days_until_renewal": self.days_until_renewal
        }


class SubscriptionItem(Base):
    """Individual items within a subscription."""
    
    __tablename__ = "subscription_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    
    # Item details
    item_type = Column(String(50), nullable=False)  # 'plan', 'addon', 'overage'
    item_id = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    
    # Pricing
    unit_price = Column(Float, nullable=False)
    currency = Column(String(3), default="KES")
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)