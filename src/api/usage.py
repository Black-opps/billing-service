"""
Usage metering API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from ..core.database import get_db
from ..core.security import get_current_user, require_permission
from ..services.metering import UsageMeteringService
from ..models.user import User
from ..schemas.usage import (
    UsageRecordCreate,
    UsageRecordResponse,
    UsageSummaryResponse,
    UsageAlertResponse
)

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("/track", status_code=201)
async def track_usage(
    usage_data: UsageRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("track:usage"))
):
    """Track a usage event."""
    metering = UsageMeteringService(db)
    
    try:
        record = await metering.track_usage(
            tenant_id=usage_data.tenant_id,
            metric_name=usage_data.metric_name,
            quantity=usage_data.quantity,
            service=usage_data.service,
            metadata=usage_data.metadata,
            idempotency_key=usage_data.idempotency_key
        )
        
        return {"message": "Usage tracked", "id": str(record.id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{tenant_id}")
async def get_current_usage(
    tenant_id: UUID,
    metric_name: str = Query(..., description="Metric name"),
    period: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current usage for a metric."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    metering = UsageMeteringService(db)
    
    usage = await metering.get_current_usage(
        tenant_id=tenant_id,
        metric_name=metric_name,
        period=period
    )
    
    return {
        "tenant_id": str(tenant_id),
        "metric_name": metric_name,
        "period": period or datetime.utcnow().strftime("%Y-%m"),
        "usage": usage
    }


@router.get("/summary/{tenant_id}", response_model=UsageSummaryResponse)
async def get_usage_summary(
    tenant_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage summary for a time period."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not start_date:
        start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    if not end_date:
        end_date = datetime.utcnow()
    
    metering = UsageMeteringService(db)
    
    summary = await metering.get_usage_summary(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get limits
    limits = await metering.get_tenant_limits(tenant_id)
    
    return {
        "tenant_id": str(tenant_id),
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "usage": summary,
        "limits": limits
    }


@router.get("/limits/{tenant_id}")
async def get_usage_limits(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage limits for tenant."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    metering = UsageMeteringService(db)
    
    limits = await metering.get_tenant_limits(tenant_id)
    
    # Get current usage for each limit
    current_usage = {}
    for metric in limits.keys():
        usage = await metering.get_current_usage(tenant_id, metric)
        current_usage[metric] = usage
    
    return {
        "tenant_id": str(tenant_id),
        "limits": limits,
        "current_usage": current_usage
    }


@router.post("/check/{tenant_id}")
async def check_usage_limits(
    tenant_id: UUID,
    metrics: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if tenant has capacity for requested usage."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    metering = UsageMeteringService(db)
    
    has_capacity = await metering.check_usage_limits(tenant_id, metrics)
    
    return {
        "tenant_id": str(tenant_id),
        "has_capacity": has_capacity,
        "checked_metrics": metrics
    }


@router.get("/alerts/{tenant_id}", response_model=List[UsageAlertResponse])
async def get_usage_alerts(
    tenant_id: UUID,
    pending_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage alerts for tenant."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    metering = UsageMeteringService(db)
    
    if pending_only:
        alerts = await metering.get_pending_alerts(tenant_id)
    else:
        # Get all alerts from database
        alerts = db.query(UsageAlert).filter(
            UsageAlert.tenant_id == tenant_id
        ).order_by(UsageAlert.created_at.desc()).limit(100).all()
    
    return alerts


@router.post("/alerts/{tenant_id}/mark-sent")
async def mark_alerts_sent(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all pending alerts as sent."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    metering = UsageMeteringService(db)
    await metering.mark_alerts_sent(tenant_id)
    
    return {"message": "Alerts marked as sent"}