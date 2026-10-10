"""
Pricing service for plans, limits, and calculations.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.plan import DEFAULT_PLANS, BillingInterval, Plan
from ..models.subscription import Subscription, SubscriptionStatus
from ..models.usage import Usage
from ..schemas.plan import PlanCreate, PlanResponse, PlanUpdate

logger = logging.getLogger(__name__)


class PricingService:
    """Service for pricing calculations and plan management"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Plan Management ====================

    def get_all_plans(self, skip: int = 0, limit: int = 100) -> List[Plan]:
        """Get all active plans"""
        return (
            self.db.query(Plan)
            .filter(Plan.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by plan_id"""
        return self.db.query(Plan).filter(Plan.plan_id == plan_id).first()

    def get_plan_by_id(self, plan_uuid: str) -> Optional[Plan]:
        """Get a plan by UUID"""
        return self.db.query(Plan).filter(Plan.id == plan_uuid).first()

    def create_plan(self, plan_data: PlanCreate) -> Plan:
        """Create a new plan"""
        # Convert interval string to enum
        interval_value = (
            plan_data.billing_interval
            if hasattr(plan_data, "billing_interval")
            else "monthly"
        )
        interval_enum = (
            BillingInterval(interval_value)
            if interval_value in [e.value for e in BillingInterval]
            else BillingInterval.MONTHLY
        )

        plan = Plan(
            id=str(uuid.uuid4()),
            plan_id=plan_data.plan_id,
            name=plan_data.name,
            description=plan_data.description,
            price=plan_data.price,
            currency=plan_data.currency or "KES",
            interval=interval_enum,
            features=plan_data.features or [],
            limits=plan_data.limits or {},
            is_active=plan_data.is_active if hasattr(plan_data, "is_active") else True,
            badge=plan_data.badge if hasattr(plan_data, "badge") else None,
            display_order=(
                plan_data.display_order if hasattr(plan_data, "display_order") else 0
            ),
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        logger.info(f"✅ Created plan: {plan.plan_id} - {plan.name}")
        return plan

    def update_plan(self, plan_id: str, plan_data: PlanUpdate) -> Optional[Plan]:
        """Update an existing plan"""
        plan = self.get_plan(plan_id)
        if not plan:
            logger.warning(f"Plan '{plan_id}' not found for update")
            return None

        update_data = plan_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            # Handle interval separately as it's an enum
            if key == "billing_interval" and value:
                plan.interval = BillingInterval(value)
            elif key == "interval":
                # Skip if it's the old field name
                continue
            else:
                setattr(plan, key, value)

        self.db.commit()
        self.db.refresh(plan)
        logger.info(f"✅ Updated plan: {plan.plan_id} - {plan.name}")
        return plan

    def delete_plan(self, plan_id: str) -> bool:
        """Soft delete a plan (mark as inactive)"""
        plan = self.get_plan(plan_id)
        if not plan:
            logger.warning(f"Plan '{plan_id}' not found for deletion")
            return False

        plan.is_active = False
        self.db.commit()
        logger.info(f"✅ Deleted plan: {plan.plan_id} - {plan.name}")
        return True

    def seed_default_plans(self):
        """Seed default plans if none exist"""
        existing = self.db.query(Plan).first()
        if existing:
            logger.info("Plans already seeded, skipping...")
            return

        count = 0
        for plan_data in DEFAULT_PLANS:
            # Convert interval string to enum
            interval_str = plan_data.get("interval", "monthly")
            interval_enum = (
                BillingInterval(interval_str)
                if interval_str in [e.value for e in BillingInterval]
                else BillingInterval.MONTHLY
            )

            plan = Plan(
                id=str(uuid.uuid4()),
                plan_id=plan_data["plan_id"],
                name=plan_data["name"],
                description=plan_data["description"],
                price=plan_data["price"],
                currency=plan_data.get("currency", "KES"),
                interval=interval_enum,
                features=plan_data.get("features", []),
                limits=plan_data.get("limits", {}),
                is_active=True,
                badge=plan_data.get("badge"),
                display_order=plan_data.get("display_order", 0),
            )
            self.db.add(plan)
            count += 1

        self.db.commit()
        logger.info(f"✅ Seeded {count} default plans")

    # ==================== Plan Limits & Features ====================

    def get_plan_limits(self, plan_id: str) -> Dict[str, Any]:
        """Get limits for a plan by plan_id"""

        # Check database first
        plan = (
            self.db.query(Plan)
            .filter(Plan.plan_id == plan_id, Plan.is_active == True)
            .first()
        )

        if plan and plan.limits:
            return plan.limits

        # Fallback to DEFAULT_PLANS
        for default_plan in DEFAULT_PLANS:
            if default_plan["plan_id"] == plan_id:
                return default_plan.get("limits", {})

        # Return free plan limits
        return {"transactions": 100, "users": 1, "reports": 5}

    def get_plan_features(self, plan_id: str) -> List[str]:
        """Get features for a plan by plan_id"""

        plan = (
            self.db.query(Plan)
            .filter(Plan.plan_id == plan_id, Plan.is_active == True)
            .first()
        )

        if plan and plan.features:
            return plan.features

        for default_plan in DEFAULT_PLANS:
            if default_plan["plan_id"] == plan_id:
                return default_plan.get("features", [])

        return []

    def get_plan_price(self, plan_id: str) -> float:
        """Get price for a plan"""

        plan = (
            self.db.query(Plan)
            .filter(Plan.plan_id == plan_id, Plan.is_active == True)
            .first()
        )

        if plan:
            return plan.price

        for default_plan in DEFAULT_PLANS:
            if default_plan["plan_id"] == plan_id:
                return default_plan.get("price", 0)

        return 0

    # ==================== Overage & Billing Calculations ====================

    def calculate_overage_charge(
        self, overage: int, plan_id: str, metric: str = "transactions"
    ) -> float:
        """Calculate overage charge"""

        limits = self.get_plan_limits(plan_id)
        limit = limits.get(metric, 0)

        if limit == 0:
            return 0.0

        # Overage pricing: KES 0.10 per transaction over limit
        # Can be configurable per plan
        if metric == "transactions":
            return overage * 0.10
        elif metric == "uploads":
            return overage * 50.00
        elif metric == "exports":
            return overage * 20.00

        return 0.0

    def calculate_historical_backfill_price(self, months: int) -> float:
        """Calculate price for historical backfill"""

        if months <= 0:
            return 0.0
        elif months <= 3:
            return 300.0
        elif months <= 6:
            return 500.0
        elif months <= 12:
            return 1000.0
        elif months <= 24:
            return 1500.0
        else:
            return 2500.0

    def calculate_monthly_invoice(
        self, tenant_id: str, usage: Dict[str, Any], plan_id: str
    ) -> Dict[str, Any]:
        """Calculate monthly invoice for a tenant"""

        limits = self.get_plan_limits(plan_id)
        base_price = self.get_plan_price(plan_id)

        max_transactions = limits.get("transactions", 0)

        total = base_price
        items = []

        # Add base subscription
        items.append(
            {
                "description": f"{plan_id.capitalize()} Plan - Monthly Subscription",
                "amount": base_price,
                "type": "subscription",
            }
        )

        # Check for overages
        if (
            max_transactions > 0
            and usage.get("transactions_processed", 0) > max_transactions
        ):
            overage = usage.get("transactions_processed", 0) - max_transactions
            overage_charge = self.calculate_overage_charge(overage, plan_id)

            if overage_charge > 0:
                items.append(
                    {
                        "description": f"Overage - {overage} transactions over limit",
                        "amount": overage_charge,
                        "type": "overage",
                        "details": {
                            "limit": max_transactions,
                            "actual": usage.get("transactions_processed", 0),
                            "overage": overage,
                        },
                    }
                )
                total += overage_charge

        # Check for historical backfill charges
        if usage.get("historical_months_imported", 0) > 0:
            historical_months = usage.get("historical_months_imported", 0)
            included_months = limits.get("historical_months", 0)

            if included_months and historical_months > included_months:
                extra_months = historical_months - included_months
                backfill_charge = self.calculate_historical_backfill_price(extra_months)

                if backfill_charge > 0:
                    items.append(
                        {
                            "description": f"Historical Backfill - {extra_months} months",
                            "amount": backfill_charge,
                            "type": "historical_backfill",
                            "details": {
                                "included_months": included_months,
                                "actual_months": historical_months,
                                "extra_months": extra_months,
                            },
                        }
                    )
                    total += backfill_charge

        return {
            "total": total,
            "currency": "KES",
            "items": items,
            "plan": plan_id,
            "period": usage.get("period", ""),
        }

    # ==================== Subscription Helpers ====================

    def get_subscription_plan(self, subscription: Subscription) -> Optional[Plan]:
        """Get the plan for a subscription"""
        if not subscription:
            return None

        return self.get_plan_by_id(subscription.plan_id)

    def is_plan_feature_enabled(self, plan_id: str, feature: str) -> bool:
        """Check if a specific feature is enabled for a plan"""
        features = self.get_plan_features(plan_id)
        return feature in features

    def get_plan_display_info(self, plan_id: str) -> Dict[str, Any]:
        """Get display information for a plan"""
        plan = self.get_plan(plan_id)
        if not plan:
            return {}

        return {
            "id": plan.plan_id,
            "name": plan.name,
            "description": plan.description,
            "price": plan.price,
            "currency": plan.currency,
            "interval": plan.interval.value if plan.interval else "monthly",
            "features": plan.features,
            "badge": plan.badge,
            "is_active": plan.is_active,
        }
