"""
Usage metering service.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from uuid import UUID
import json

from ..models.usage import UsageRecord, UsageAlert, UsageAggregate, MetricType
from ..models.subscription import Subscription
from ..core.exceptions import MeteringError
from ..core.database import BillingCache
from ..core.config import settings

logger = logging.getLogger(__name__)


class UsageMeteringService:
    """Service for tracking and metering usage."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cache = BillingCache()
    
    async def track_usage(
        self,
        tenant_id: UUID,
        metric_name: str,
        quantity: int = 1,
        service: str = "api",
        metadata: dict = None,
        idempotency_key: str = None
    ) -> UsageRecord:
        """
        Track a usage event.
        
        Args:
            tenant_id: Tenant UUID
            metric_name: Name of metric (e.g., 'transactions_parsed')
            quantity: Amount to add
            service: Service generating the event
            metadata: Additional metadata
            idempotency_key: For deduplication
            
        Returns:
            Created usage record
        """
        # Check for duplicate if idempotency key provided
        if idempotency_key:
            existing = self.db.query(UsageRecord).filter(
                UsageRecord.idempotency_key == idempotency_key
            ).first()
            if existing:
                logger.info(f"Duplicate usage event: {idempotency_key}")
                return existing
        
        now = datetime.utcnow()
        period = now.strftime("%Y-%m")
        
        # Create usage record
        record = UsageRecord(
            tenant_id=tenant_id,
            metric_name=metric_name,
            quantity=quantity,
            timestamp=now,
            period=period,
            service=service,
            metadata=metadata or {},
            idempotency_key=idempotency_key
        )
        
        self.db.add(record)
        
        # Update aggregate
        await self._update_aggregate(tenant_id, metric_name, period, quantity, service)
        
        # Check thresholds
        await self._check_usage_thresholds(tenant_id, metric_name)
        
        self.db.commit()
        
        logger.info(f"Tracked usage: {tenant_id} - {metric_name} +{quantity}")
        
        return record
    
    async def _update_aggregate(
        self,
        tenant_id: UUID,
        metric_name: str,
        period: str,
        quantity: int,
        service: str
    ):
        """Update usage aggregates."""
        aggregate = self.db.query(UsageAggregate).filter(
            and_(
                UsageAggregate.tenant_id == tenant_id,
                UsageAggregate.metric_name == metric_name,
                UsageAggregate.period == period
            )
        ).first()
        
        if not aggregate:
            aggregate = UsageAggregate(
                tenant_id=tenant_id,
                metric_name=metric_name,
                period=period,
                total=0,
                by_service={}
            )
            self.db.add(aggregate)
        
        aggregate.total += quantity
        
        # Update service breakdown
        by_service = aggregate.by_service or {}
        by_service[service] = by_service.get(service, 0) + quantity
        aggregate.by_service = by_service
        
        # Invalidate cache
        self.cache.set_usage(str(tenant_id), metric_name, period, {
            "total": aggregate.total,
            "by_service": by_service
        })
    
    async def _check_usage_thresholds(self, tenant_id: UUID, metric_name: str):
        """Check if usage has crossed any thresholds."""
        # Get current usage
        current = await self.get_current_usage(tenant_id, metric_name)
        
        # Get subscription limits
        subscription = self.db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status.in_(['active', 'trialing'])
        ).first()
        
        if not subscription or not subscription.plan:
            return
        
        plan_limits = subscription.plan.limits or {}
        limit = plan_limits.get(metric_name, 0)
        
        if limit == 0:
            return  # Unlimited or not tracked
        
        # Check each threshold
        for threshold in settings.USAGE_ALERT_THRESHOLDS:
            if current >= limit * threshold:
                # Check if alert already sent
                existing = self.db.query(UsageAlert).filter(
                    and_(
                        UsageAlert.tenant_id == tenant_id,
                        UsageAlert.metric_name == metric_name,
                        UsageAlert.threshold == threshold,
                        UsageAlert.is_sent == True
                    )
                ).first()
                
                if not existing:
                    # Create alert
                    alert = UsageAlert(
                        tenant_id=tenant_id,
                        subscription_id=subscription.id,
                        metric_name=metric_name,
                        threshold=threshold,
                        current_usage=current,
                        limit=limit
                    )
                    self.db.add(alert)
                    
                    logger.info(f"Usage alert for {tenant_id}: {metric_name} at {threshold*100}%")
    
    async def get_current_usage(
        self,
        tenant_id: UUID,
        metric_name: str,
        period: str = None
    ) -> int:
        """Get current usage for a metric."""
        if not period:
            period = datetime.utcnow().strftime("%Y-%m")
        
        # Try cache first
        cached = self.cache.get_usage(str(tenant_id), metric_name, period)
        if cached:
            return cached.get("total", 0)
        
        # Query database
        result = self.db.query(func.sum(UsageRecord.quantity)).filter(
            and_(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.metric_name == metric_name,
                UsageRecord.period == period
            )
        ).scalar()
        
        total = result or 0
        
        # Cache for next time
        self.cache.set_usage(str(tenant_id), metric_name, period, {"total": total})
        
        return total
    
    async def get_usage_summary(
        self,
        tenant_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get usage summary for a time period."""
        records = self.db.query(UsageRecord).filter(
            and_(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.timestamp >= start_date,
                UsageRecord.timestamp <= end_date
            )
        ).all()
        
        summary = {}
        
        for record in records:
            if record.metric_name not in summary:
                summary[record.metric_name] = {
                    "total": 0,
                    "by_service": {},
                    "by_day": {}
                }
            
            metric_summary = summary[record.metric_name]
            metric_summary["total"] += record.quantity
            
            # By service
            service = record.service
            metric_summary["by_service"][service] = \
                metric_summary["by_service"].get(service, 0) + record.quantity
            
            # By day
            day = record.timestamp.strftime("%Y-%m-%d")
            metric_summary["by_day"][day] = \
                metric_summary["by_day"].get(day, 0) + record.quantity
        
        return summary
    
    async def get_tenant_limits(self, tenant_id: UUID) -> Dict:
        """Get usage limits for tenant."""
        subscription = self.db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status.in_(['active', 'trialing'])
        ).first()
        
        if not subscription or not subscription.plan:
            return {}
        
        return subscription.plan.limits or {}
    
    async def check_usage_limits(self, tenant_id: UUID, metrics: Dict[str, int]) -> bool:
        """
        Check if tenant has capacity for requested usage.
        
        Args:
            tenant_id: Tenant UUID
            metrics: Dict of metric_name -> requested quantity
            
        Returns:
            True if under limits, False if any limit exceeded
        """
        limits = await self.get_tenant_limits(tenant_id)
        
        for metric_name, requested in metrics.items():
            if metric_name not in limits:
                continue  # No limit for this metric
            
            current = await self.get_current_usage(tenant_id, metric_name)
            limit = limits[metric_name]
            
            if current + requested > limit:
                logger.warning(f"Usage limit exceeded for {tenant_id}: {metric_name} {current+requested}>{limit}")
                return False
        
        return True
    
    async def get_pending_alerts(self, tenant_id: UUID) -> List[Dict]:
        """Get pending usage alerts for tenant."""
        alerts = self.db.query(UsageAlert).filter(
            UsageAlert.tenant_id == tenant_id,
            UsageAlert.is_sent == False
        ).all()
        
        return [{
            "metric": alert.metric_name,
            "threshold": alert.threshold,
            "current_usage": alert.current_usage,
            "limit": alert.limit,
            "percentage": (alert.current_usage / alert.limit) * 100
        } for alert in alerts]
    
    async def mark_alerts_sent(self, tenant_id: UUID):
        """Mark all pending alerts as sent."""
        self.db.query(UsageAlert).filter(
            UsageAlert.tenant_id == tenant_id,
            UsageAlert.is_sent == False
        ).update({"is_sent": True, "sent_at": datetime.utcnow()})
        
        self.db.commit()
    
    async def reset_monthly_usage(self):
        """Reset monthly usage aggregates (called at month end)."""
        # Archive old aggregates if needed
        last_month = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m")
        
        # Delete old usage records (optional - depends on retention policy)
        # self.db.query(UsageRecord).filter(UsageRecord.period < last_month).delete()
        
        logger.info(f"Reset monthly usage for period {last_month}")