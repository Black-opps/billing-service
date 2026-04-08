"""
Subscriptions API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from ..core.database import get_db
from ..core.security import require_permission, get_current_tenant
from ..services.billing_cycle import BillingCycleService
from ..schemas.subscription import SubscriptionResponse, SubscriptionCreate, SubscriptionUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("/", response_model=SubscriptionResponse)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    """Create a new subscription for a tenant."""
    billing_service = BillingCycleService(db)
    new_subscription = billing_service.create_subscription(
        tenant_id=subscription.tenant_id,
        plan_id=subscription.plan_id,
        billing_period=subscription.billing_period
    )
    return new_subscription


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    """Get subscription by ID."""
    billing_service = BillingCycleService(db)
    subscription = billing_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check access
    if subscription.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return subscription


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    subscription: SubscriptionUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    """Update subscription."""
    billing_service = BillingCycleService(db)
    updated = billing_service.update_subscription(subscription_id, subscription)
    if not updated:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return updated


@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant)
):
    """Cancel subscription."""
    billing_service = BillingCycleService(db)
    result = billing_service.cancel_subscription(subscription_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription cancelled successfully"}