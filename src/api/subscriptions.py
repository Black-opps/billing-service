"""
Subscription management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ..core.database import get_db
from ..core.security import get_current_user, require_permission
from ..services.billing_cycle import BillingCycleService
from ..services.pricing import PricingService
from ..models.subscription import Subscription, SubscriptionStatus
from ..models.user import User
from ..schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionUpgrade,
    SubscriptionCancel
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("/", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    sub_data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new subscription."""
    # Check tenant access
    if current_user.tenant_id != sub_data.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pricing = PricingService(db)
    
    # Get plan
    plan = await pricing.get_plan(sub_data.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Calculate dates
    now = datetime.utcnow()
    if sub_data.billing_cycle == "monthly":
        period_end = now.replace(day=1) + timedelta(days=32)
        period_end = period_end.replace(day=1) - timedelta(days=1)
    elif sub_data.billing_cycle == "yearly":
        period_end = now.replace(year=now.year + 1, month=now.month, day=now.day)
    else:
        period_end = now + timedelta(days=30)
    
    # Create subscription
    subscription = Subscription(
        tenant_id=sub_data.tenant_id,
        plan_id=plan.id,
        status=SubscriptionStatus.TRIALING if sub_data.has_trial else SubscriptionStatus.ACTIVE,
        billing_cycle=sub_data.billing_cycle,
        unit_price=plan.price,
        quantity=sub_data.quantity or 1,
        current_period_start=now,
        current_period_end=period_end,
        trial_end=now + timedelta(days=14) if sub_data.has_trial else None,
        auto_renew=sub_data.auto_renew
    )
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    return subscription


@router.get("/tenant/{tenant_id}", response_model=List[SubscriptionResponse])
async def get_tenant_subscriptions(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all subscriptions for a tenant."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    subscriptions = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id
    ).all()
    
    return subscriptions


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get subscription details."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check access
    if current_user.tenant_id != subscription.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return subscription


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    sub_data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:billing"))
):
    """Update subscription."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check access
    if current_user.tenant_id != subscription.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in sub_data.dict(exclude_unset=True).items():
        setattr(subscription, key, value)
    
    subscription.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(subscription)
    
    return subscription


@router.post("/{subscription_id}/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    subscription_id: UUID,
    upgrade_data: SubscriptionUpgrade,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:billing"))
):
    """Upgrade subscription to a new plan."""
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check access
    if current_user.tenant_id != subscription.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    pricing = PricingService(db)
    
    # Get new plan
    new_plan = await pricing.get_plan(upgrade_data.new_plan_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="New plan not found")
    
    # Calculate proration
    proration = await pricing.calculate_proration(
        subscription_id=subscription_id,
        new_plan_id=upgrade_data.new_plan_id,
        effective_date=upgrade_data.effective_date
    )
    
    # Update subscription
    subscription.plan_id = new_plan.id
    subscription.unit_price = new_plan.price
    subscription.metadata["upgrade"] = {
        "from_plan": str(subscription.plan_id),
        "to_plan": new_plan.plan_id,
        "proration": proration,
        "upgraded_at": datetime.utcnow().isoformat()
    }
    
    db.commit()
    db.refresh(subscription)
    
    return subscription


@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: UUID,
    cancel_data: SubscriptionCancel,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:billing"))
):
    """Cancel a subscription."""
    billing = BillingCycleService(db)
    
    try:
        subscription = await billing.cancel_subscription(
            subscription_id=subscription_id,
            cancel_immediately=cancel_data.immediate
        )
        
        return {
            "message": "Subscription canceled successfully",
            "subscription_id": str(subscription_id),
            "effective_date": subscription.current_period_end if not cancel_data.immediate else datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:billing"))
):
    """Reactivate a canceled subscription."""
    billing = BillingCycleService(db)
    
    try:
        subscription = await billing.reactivate_subscription(subscription_id)
        return subscription
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{subscription_id}/status")
async def check_subscription_status(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check subscription status."""
    billing = BillingCycleService(db)
    
    try:
        status = await billing.check_subscription_status(subscription_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))