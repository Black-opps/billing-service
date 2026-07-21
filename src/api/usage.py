"""
Usage metering API endpoints.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_tenant, require_permission
from ..schemas.usage import UsageAlertResponse, UsageRecordCreate, UsageSummaryResponse
from ..services.metering import UsageMeteringService

router = APIRouter(prefix="/usage", tags=["Usage"])


# ==================== PUBLIC TEST ENDPOINTS ====================


@router.get("/public/test")
async def usage_test():
    """Public test endpoint to verify usage router is working."""
    return {
        "status": "ok",
        "message": "Usage router is working!",
        "endpoints": [
            "POST /track - Track usage (auth required)",
            "GET /current/{tenant_id} - Get current usage (auth required)",
            "GET /summary/{tenant_id} - Get usage summary (auth required)",
            "GET /limits/{tenant_id} - Get usage limits (auth required)",
            "POST /check/{tenant_id} - Check usage limits (auth required)",
        ],
    }


@router.get("/public/stats")
async def usage_stats(db: Session = Depends(get_db)):
    """Public endpoint to check if usage data exists."""
    from ..models.usage import Usage

    total_records = db.query(Usage).count()
    latest = db.query(Usage).order_by(Usage.created_at.desc()).first()

    return {
        "status": "ok",
        "total_usage_records": total_records,
        "latest_record": (
            {
                "tenant_id": latest.tenant_id if latest else None,
                "billing_period": latest.billing_period if latest else None,
                "transactions_processed": (
                    latest.transactions_processed if latest else 0
                ),
            }
            if latest
            else None
        ),
        "message": (
            "No usage data recorded yet" if total_records == 0 else "Usage data exists"
        ),
    }


# ==================== AUTHENTICATED ENDPOINTS ====================


@router.post("/track", status_code=201)
async def track_usage(
    usage_data: UsageRecordCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
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
            idempotency_key=usage_data.idempotency_key,
        )

        return {"message": "Usage tracked", "id": str(record.id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{tenant_id}")
async def get_current_usage(
    tenant_id: str,
    metric_name: str = Query(..., description="Metric name"),
    period: Optional[str] = None,
    db: Session = Depends(get_db),
    current_tenant_id: str = Depends(get_current_tenant),
):
    """Get current usage for a metric."""
    # Check access
    if current_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metering = UsageMeteringService(db)

    usage = await metering.get_current_usage(
        tenant_id=tenant_id, metric_name=metric_name, period=period
    )

    return {
        "tenant_id": str(tenant_id),
        "metric_name": metric_name,
        "period": period or datetime.utcnow().strftime("%Y-%m"),
        "usage": usage,
    }


@router.get("/summary/{tenant_id}", response_model=UsageSummaryResponse)
async def get_usage_summary(
    tenant_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_tenant_id: str = Depends(get_current_tenant),
):
    """Get usage summary for a time period."""
    # Check access
    if current_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not start_date:
        start_date = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

    if not end_date:
        end_date = datetime.utcnow()

    metering = UsageMeteringService(db)

    summary = await metering.get_usage_summary(
        tenant_id=tenant_id, start_date=start_date, end_date=end_date
    )

    # Get limits
    limits = await metering.get_tenant_limits(tenant_id)

    return {
        "tenant_id": str(tenant_id),
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "usage": summary,
        "limits": limits,
    }


@router.get("/limits/{tenant_id}")
async def get_usage_limits(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_tenant_id: str = Depends(get_current_tenant),
):
    """Get usage limits for tenant."""
    # Check access
    if current_tenant_id != tenant_id:
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
        "current_usage": current_usage,
    }


@router.post("/check/{tenant_id}")
async def check_usage_limits(
    tenant_id: str,
    metrics: dict,
    db: Session = Depends(get_db),
    current_tenant_id: str = Depends(get_current_tenant),
):
    """Check if tenant has capacity for requested usage."""
    # Check access
    if current_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    metering = UsageMeteringService(db)

    has_capacity = await metering.check_usage_limits(tenant_id, metrics)

    return {
        "tenant_id": str(tenant_id),
        "has_capacity": has_capacity,
        "checked_metrics": metrics,
    }
