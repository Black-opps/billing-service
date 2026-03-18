"""
Plan management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..core.database import get_db
from ..core.security import require_permission
from ..services.pricing import PricingService
from ..models.plan import Plan
from ..schemas.plan import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PriceCalculationRequest,
    PriceCalculationResponse
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/", response_model=List[PlanResponse])
async def list_plans(
    include_hidden: bool = Query(False, description="Include hidden plans"),
    db: Session = Depends(get_db)
):
    """List all available plans."""
    service = PricingService(db)
    plans = await service.list_plans(include_hidden=include_hidden)
    return plans


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """Get plan details by ID."""
    service = PricingService(db)
    plan = await service.get_plan(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return plan


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    plan_data: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin:plans"))
):
    """Create a new plan (admin only)."""
    service = PricingService(db)
    
    # Check if plan already exists
    existing = await service.get_plan(plan_data.plan_id)
    if existing:
        raise HTTPException(status_code=400, detail="Plan with this ID already exists")
    
    plan = Plan(**plan_data.dict())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    return plan


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str,
    plan_data: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin:plans"))
):
    """Update a plan (admin only)."""
    service = PricingService(db)
    plan = await service.get_plan(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    for key, value in plan_data.dict(exclude_unset=True).items():
        setattr(plan, key, value)
    
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    
    return plan


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin:plans"))
):
    """Delete a plan (admin only)."""
    service = PricingService(db)
    plan = await service.get_plan(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Soft delete
    plan.is_active = False
    db.commit()
    
    return None


@router.post("/calculate-price", response_model=PriceCalculationResponse)
async def calculate_price(
    request: PriceCalculationRequest,
    db: Session = Depends(get_db)
):
    """Calculate price for a subscription."""
    service = PricingService(db)
    
    try:
        calculation = await service.calculate_subscription_price(
            plan_id=request.plan_id,
            quantity=request.quantity,
            coupon_code=request.coupon_code,
            interval=request.interval
        )
        return calculation
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/initialize", status_code=201)
async def initialize_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin:plans"))
):
    """Initialize default plans (admin only)."""
    service = PricingService(db)
    await service.initialize_plans()
    
    return {"message": "Default plans initialized"}