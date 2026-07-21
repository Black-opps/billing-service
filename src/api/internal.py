# billing-service/src/api/internal.py
"""
Internal API for service-to-service communication.
Uses X-Service-Key instead of JWT authentication.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.models.plan import BillingInterval, Plan
from src.models.subscription import Subscription, SubscriptionStatus
from src.services.metering import UsageMeteringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal"])

# Get service token from environment
SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "your-internal-service-token-123")


# ==================== Pydantic Models ====================


class UsageTrackRequest(BaseModel):
    """Request model for tracking usage."""

    tenant_id: str
    metric_name: str
    quantity: int = 1
    service: str = "api"
    metadata: Optional[Dict] = None


# ==================== Helper Functions ====================


def verify_service_token(x_service_key: str = Header(...)):
    """Verify internal service token."""
    if x_service_key != SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid service token")
    return True


def get_or_create_free_plan(db: Session):
    """Get or create the free plan with a proper UUID."""
    # Try to find existing free plan
    plan = db.query(Plan).filter(Plan.name == "Free").first()

    if not plan:
        # Create new free plan with UUID
        plan_id = str(uuid.uuid4())
        plan = Plan(
            id=plan_id,
            name="Free",
            description="Free tier for testing",
            price=0,
            billing_interval="monthly",
            limits={"transactions": 10000, "uploads": 100},
            is_active=True,
            is_public=True,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        print(f"✅ Created Free plan with ID: {plan.id}")

    return plan


# ==================== Endpoints ====================


@router.post("/usage/check/{tenant_id}")
async def internal_check_usage(
    tenant_id: str,
    metrics: dict,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_token),
):
    """Internal endpoint for checking usage limits (no JWT required)."""
    metering = UsageMeteringService(db)

    # Check if subscription exists for this tenant
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .first()
    )

    # If no subscription exists, create a free one
    if not subscription:
        plan = get_or_create_free_plan(db)

        # Create subscription with correct field names
        subscription = Subscription(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle=BillingInterval.MONTHLY,
            unit_price=0,
            quantity=1,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            auto_renew=True,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        print(f"✅ Auto-created subscription for tenant: {tenant_id}")

    # Check usage limits
    has_capacity = await metering.check_usage_limits(tenant_id, metrics)

    # Get current usage
    limits = await metering.get_tenant_limits(tenant_id)
    current_usage = {}
    for metric in metrics.keys():
        usage = await metering.get_current_usage(tenant_id, metric)
        current_usage[metric] = usage

    # Get remaining
    remaining = {}
    for metric, value in current_usage.items():
        limit = limits.get(metric, 0)
        remaining[metric] = max(0, limit - value)

    return {
        "tenant_id": tenant_id,
        "has_capacity": has_capacity,
        "checked_metrics": metrics,
        "current_usage": current_usage,
        "limits": limits,
        "remaining": remaining,
        "plan": subscription.plan_id,
        "subscription_status": subscription.status.value,
    }


@router.post("/usage/track")
async def internal_track_usage(
    request: UsageTrackRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_token),
):
    """
    Internal endpoint for tracking usage (no JWT required).

    Expects JSON body with:
    - tenant_id: str (required)
    - metric_name: str (required)
    - quantity: int (default: 1)
    - service: str (default: "api")
    - metadata: dict (optional)
    """
    metering = UsageMeteringService(db)

    # Log what we're tracking
    logger.info(
        f"📊 Tracking usage: tenant={request.tenant_id}, metric={request.metric_name}, quantity={request.quantity}"
    )

    # Track usage
    event = await metering.track_usage(
        tenant_id=request.tenant_id,
        metric_name=request.metric_name,
        quantity=request.quantity,
        service=request.service,
        metadata=request.metadata or {},
    )

    return {
        "success": True,
        "event_id": event.id,
        "tenant_id": request.tenant_id,
        "metric_name": request.metric_name,
        "quantity": request.quantity,
    }


@router.get("/usage/summary/{tenant_id}")
async def internal_get_usage_summary(
    tenant_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_token),
):
    """Get usage summary (no JWT required)."""
    metering = UsageMeteringService(db)

    # Get current period
    from datetime import datetime

    start_date = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end_date = datetime.utcnow()

    summary = await metering.get_usage_summary(tenant_id, start_date, end_date)
    limits = await metering.get_tenant_limits(tenant_id)

    return {"tenant_id": tenant_id, "summary": summary, "limits": limits}
