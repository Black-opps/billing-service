"""
Plans API endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_tenant, require_permission
from ..schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from ..services.pricing import PricingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


def format_plan_response(plan) -> dict:
    """Format a plan object for API response."""
    return {
        "id": str(plan.id),
        "plan_id": plan.plan_id,
        "name": plan.name,
        "description": plan.description,
        "price": plan.price,
        "currency": plan.currency,
        "billing_interval": plan.interval.value if plan.interval else "monthly",
        "features": plan.features,
        "limits": plan.limits,
        "is_active": plan.is_active,
        "is_public": plan.is_public,
        "badge": plan.badge,
        "display_order": plan.display_order,
        "created_at": (
            plan.created_at.isoformat()
            if plan.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": (
            plan.updated_at.isoformat()
            if plan.updated_at
            else datetime.utcnow().isoformat()
        ),
    }


@router.get("", response_model=List[PlanResponse])  # No trailing slash
@router.get("/", response_model=List[PlanResponse])  # With trailing slash
async def list_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """List all available plans."""
    pricing_service = PricingService(db)
    plans = pricing_service.get_all_plans(skip=skip, limit=limit)

    return [format_plan_response(p) for p in plans]


@router.get("/active", response_model=List[PlanResponse])
async def get_active_plans(
    tenant_id: str = Depends(get_current_tenant), db: Session = Depends(get_db)
):
    """
    Get all active plans.

    Returns only plans where is_active is True.
    """
    from ..models.plan import Plan

    # Query active plans directly from the database
    active_plans = db.query(Plan).filter(Plan.is_active == True).all()

    return [format_plan_response(p) for p in active_plans]


@router.get("/debug")
async def debug_plans(db: Session = Depends(get_db)):
    """Debug endpoint to check plans."""
    from ..models.plan import Plan

    plans = db.query(Plan).all()
    return {
        "count": len(plans),
        "plans": [
            {
                "id": str(p.id),
                "plan_id": p.plan_id,
                "name": p.name,
                "price": p.price,
                "is_active": p.is_active,
                "interval": p.interval.value if p.interval else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
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
    from ..models.plan import Plan

    plans = (
        db.query(Plan).filter(Plan.is_active == True).offset(skip).limit(limit).all()
    )

    return [format_plan_response(p) for p in plans]


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """Get plan by ID."""
    from ..models.plan import Plan

    # Try to find by plan_id first
    plan = db.query(Plan).filter(Plan.plan_id == plan_id).first()

    # If not found, try by UUID
    if not plan:
        try:
            import uuid

            plan_uuid = uuid.UUID(plan_id)
            plan = db.query(Plan).filter(Plan.id == plan_uuid).first()
        except ValueError:
            # Not a valid UUID
            pass

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    return format_plan_response(plan)


@router.post("", response_model=PlanResponse)  # No trailing slash
@router.post("/", response_model=PlanResponse)  # With trailing slash
async def create_plan(
    plan: PlanCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(require_permission("admin:plans")),
):
    """Create a new plan (admin only)."""
    pricing_service = PricingService(db)
    new_plan = pricing_service.create_plan(plan)

    return format_plan_response(new_plan)


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

    return format_plan_response(updated_plan)


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
