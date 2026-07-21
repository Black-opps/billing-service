"""
Usage metering service - tracks and aggregates usage.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..models.plan import DEFAULT_PLANS, Plan
from ..models.subscription import Subscription
from ..models.usage import HistoricalBackfillRequest, OverageLog, Usage, UsageEvent
from ..services.pricing import PricingService

logger = logging.getLogger(__name__)


class UsageMeteringService:
    """Service for tracking and managing usage"""

    def __init__(self, db: Session):
        self.db = db
        self.pricing = PricingService(db)

    async def track_usage(
        self,
        tenant_id: str,
        metric_name: str,
        quantity: int = 1,
        service: str = "api",
        metadata: Optional[Dict] = None,
        # idempotency_key removed - not supported by UsageEvent model
    ) -> UsageEvent:
        """Track a usage event."""

        # Record usage event
        event = UsageEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type=service,
            transaction_count=quantity,
            metadata=metadata,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)

        # Update aggregate
        await self._update_aggregate(tenant_id, metric_name, quantity)

        # Check limits
        await self._check_limits(tenant_id, metric_name)

        self.db.commit()
        self.db.refresh(event)

        logger.info(f"📊 Tracked: {tenant_id} - {metric_name} +{quantity}")
        return event

    async def _update_aggregate(self, tenant_id: str, metric_name: str, quantity: int):
        """Update usage aggregate"""
        period = datetime.utcnow().strftime("%Y-%m")

        usage = (
            self.db.query(Usage)
            .filter(Usage.tenant_id == tenant_id, Usage.billing_period == period)
            .first()
        )

        if not usage:
            usage = Usage(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                billing_period=period,
                transactions_processed=0,
                statements_uploaded=0,
                exports_generated=0,
                ai_insights_generated=0,
            )
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

        # Update appropriate metric with None check
        if metric_name == "transactions":
            usage.transactions_processed = (
                usage.transactions_processed or 0
            ) + quantity
        elif metric_name == "uploads":
            usage.statements_uploaded = (usage.statements_uploaded or 0) + quantity
        elif metric_name == "exports":
            usage.exports_generated = (usage.exports_generated or 0) + quantity
        elif metric_name == "ai_insights":
            usage.ai_insights_generated = (usage.ai_insights_generated or 0) + quantity

        usage.updated_at = datetime.utcnow()
        self.db.commit()

    async def get_current_usage(
        self, tenant_id: str, metric_name: str, period: Optional[str] = None
    ) -> int:
        """Get current usage for a metric"""
        if not period:
            period = datetime.utcnow().strftime("%Y-%m")

        usage = (
            self.db.query(Usage)
            .filter(Usage.tenant_id == tenant_id, Usage.billing_period == period)
            .first()
        )

        if not usage:
            return 0

        metrics = {
            "transactions": usage.transactions_processed or 0,
            "uploads": usage.statements_uploaded or 0,
            "exports": usage.exports_generated or 0,
            "ai_insights": usage.ai_insights_generated or 0,
        }

        return metrics.get(metric_name, 0)

    async def get_tenant_limits(self, tenant_id: str) -> Dict[str, int]:
        """Get usage limits for a tenant"""

        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id, Subscription.status == "active"
            )
            .first()
        )

        if not subscription:
            return DEFAULT_PLANS[0]["limits"]

        plan = self.db.query(Plan).filter(Plan.id == subscription.plan_id).first()

        if plan and plan.limits:
            return plan.limits

        # Fallback to default
        for default_plan in DEFAULT_PLANS:
            if default_plan["plan_id"] == "free":
                return default_plan["limits"]

        return {"transactions": 100}

    async def check_usage_limits(self, tenant_id: str, metrics: Dict[str, int]) -> bool:
        """Check if tenant has capacity for requested usage"""

        limits = await self.get_tenant_limits(tenant_id)

        for metric_name, requested in metrics.items():
            limit = limits.get(metric_name, 0)

            if limit == 0:
                continue

            current = await self.get_current_usage(tenant_id, metric_name)

            if current + requested > limit:
                logger.warning(f"⚠️ Limit exceeded: {tenant_id} - {metric_name}")
                return False

        return True

    async def _check_limits(self, tenant_id: str, metric_name: str):
        """Check if any limits have been exceeded"""

        limits = await self.get_tenant_limits(tenant_id)
        limit = limits.get(metric_name, 0)

        if limit == 0:
            return

        current = await self.get_current_usage(tenant_id, metric_name)

        if current > limit:
            overage = current - limit

            # Check if overage already recorded
            existing = (
                self.db.query(OverageLog)
                .filter(
                    OverageLog.tenant_id == tenant_id,
                    OverageLog.billing_period == datetime.utcnow().strftime("%Y-%m"),
                    OverageLog.status == "pending",
                )
                .first()
            )

            if not existing:
                overage_log = OverageLog(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    billing_period=datetime.utcnow().strftime("%Y-%m"),
                    threshold=limit,
                    actual=current,
                    overage_amount=overage,
                    charge=self.pricing.calculate_overage_charge(overage, "free"),
                    status="pending",
                )
                self.db.add(overage_log)
                self.db.commit()
                logger.info(
                    f"💰 Overage recorded: {tenant_id} - {overage} transactions"
                )

    async def get_usage_summary(
        self, tenant_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, int]:
        """Get usage summary for a time period"""

        period = datetime.utcnow().strftime("%Y-%m")
        usage = (
            self.db.query(Usage)
            .filter(Usage.tenant_id == tenant_id, Usage.billing_period == period)
            .first()
        )

        if not usage:
            return {
                "transactions": 0,
                "uploads": 0,
                "exports": 0,
                "ai_insights": 0,
            }

        return {
            "transactions": usage.transactions_processed or 0,
            "uploads": usage.statements_uploaded or 0,
            "exports": usage.exports_generated or 0,
            "ai_insights": usage.ai_insights_generated or 0,
        }
