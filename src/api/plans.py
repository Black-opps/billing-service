"""
Plans API endpoints.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_tenant, require_permission
from ..schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from ..services.pricing import PricingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("/", response_model=List[PlanResponse])
async def list_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """List all available plans."""
    pricing_service = PricingService(db)
    plans = pricing_service.get_all_plans(skip=skip, limit=limit)
    return plans


@router.get("/debug")
async def debug_plans(db: Session = Depends(get_db)):
    """Debug endpoint to check plans."""
    from ..models.plan import Plan

    plans = db.query(Plan).all()
    return {
        "count": len(plans),
        "plans": [
            {"id": str(p.id), "plan_id": p.plan_id, "name": p.name, "price": p.price}
            for p in plans
        ],
    }


@router.get("/public", response_model=List[PlanResponse])
async def list_plans_public(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Public endpoint for testing - no auth required."""
    pricing_service = PricingService(db)
    plans = pricing_service.get_all_plans(skip=skip, limit=limit)
    return plans


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """Get plan by ID."""
    pricing_service = PricingService(db)
    plan = pricing_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return plan


@router.post("/", response_model=PlanResponse)
async def create_plan(
    plan: PlanCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(require_permission("admin:plans")),
):
    """Create a new plan (admin only)."""
    pricing_service = PricingService(db)
    new_plan = pricing_service.create_plan(plan)
    return new_plan


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str,
    plan: PlanUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(require_permission("admin:plans")),
):
    """Update an existing plan (admin only)."""
    pricing_service = PricingService(db)
    updated_plan = pricing_service.update_plan(plan_id, plan)
    if not updated_plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return updated_plan


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(require_permission("admin:plans")),
):
    """Delete a plan (admin only)."""
    pricing_service = PricingService(db)
    deleted = pricing_service.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return {"message": f"Plan '{plan_id}' deleted successfully"}
