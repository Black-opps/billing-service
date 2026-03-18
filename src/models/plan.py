"""
Pricing plan models.
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import enum

from ..core.database import Base


class BillingInterval(str, enum.Enum):
    """Billing intervals."""
    MONTHLY = "monthly"
    YEARLY = "yearly"
    QUARTERLY = "quarterly"


class Plan(Base):
    """Pricing plan model."""
    
    __tablename__ = "plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    plan_id = Column(String(50), unique=True, nullable=False)  # 'free', 'starter', etc.
    
    # Pricing
    price = Column(Float, nullable=False, default=0)
    currency = Column(String(3), default="KES")
    interval = Column(Enum(BillingInterval), default=BillingInterval.MONTHLY)
    
    # Features and limits
    features = Column(JSON, default=list)
    limits = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=True)
    
    # Display
    display_order = Column(Integer, default=0)
    badge = Column(String(50), nullable=True)  # 'Popular', 'Best Value', etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Plan {self.plan_id}: {self.name} - {self.price} {self.currency}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "interval": self.interval.value,
            "features": self.features,
            "limits": self.limits,
            "is_active": self.is_active,
            "badge": self.badge,
            "display_order": self.display_order
        }


# Predefined plans for seeding
DEFAULT_PLANS = [
    {
        "plan_id": "free",
        "name": "Free",
        "description": "For small businesses just starting",
        "price": 0,
        "features": [
            "Basic Analytics Dashboard",
            "100 transactions/month",
            "7-day data retention",
            "1 user included",
            "Email support"
        ],
        "limits": {
            "transactions": 100,
            "users": 1,
            "reports": 5,
            "api_calls": 0,
            "storage_days": 7
        }
    },
    {
        "plan_id": "starter",
        "name": "Starter",
        "description": "Growing businesses needing more insights",
        "price": 2900,  # KES 29
        "features": [
            "Advanced Analytics",
            "5,000 transactions/month",
            "30-day data retention",
            "3 users included",
            "Basic API Access",
            "Email & Chat support"
        ],
        "limits": {
            "transactions": 5000,
            "users": 3,
            "reports": 50,
            "api_calls": 10000,
            "storage_days": 30
        },
        "badge": "Popular"
    },
    {
        "plan_id": "professional",
        "name": "Professional",
        "description": "Established businesses needing real-time insights",
        "price": 9900,  # KES 99
        "features": [
            "Real-time Analytics",
            "50,000 transactions/month",
            "1-year data retention",
            "10 users included",
            "Full API Access",
            "Webhook Integrations",
            "Priority Support",
            "Custom Reports"
        ],
        "limits": {
            "transactions": 50000,
            "users": 10,
            "reports": 200,
            "api_calls": 100000,
            "storage_days": 365
        }
    },
    {
        "plan_id": "enterprise",
        "name": "Enterprise",
        "description": "Large organizations with custom needs",
        "price": 0,  # Custom pricing
        "features": [
            "Unlimited transactions",
            "7-year data retention",
            "Unlimited users",
            "Custom API Limits",
            "SLA Guarantee",
            "Dedicated Support",
            "On-premise Option",
            "Audit Logs",
            "SSO Integration"
        ],
        "limits": {
            "transactions": 999999999,
            "users": 9999,
            "reports": 9999,
            "api_calls": 999999999,
            "storage_days": 2555  # 7 years
        },
        "badge": "Enterprise"
    }
]