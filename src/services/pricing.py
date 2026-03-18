"""
Pricing and discount management service.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
import logging
from uuid import UUID
from datetime import datetime, timedelta

from ..models.plan import Plan, DEFAULT_PLANS
from ..models.subscription import Subscription
from ..core.exceptions import PricingError

logger = logging.getLogger(__name__)


class PricingService:
    """Service for managing pricing and discounts."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def initialize_plans(self):
        """Initialize default plans in database."""
        for plan_data in DEFAULT_PLANS:
            existing = self.db.query(Plan).filter(
                Plan.plan_id == plan_data["plan_id"]
            ).first()
            
            if not existing:
                plan = Plan(**plan_data)
                self.db.add(plan)
                logger.info(f"Created plan: {plan_data['plan_id']}")
        
        self.db.commit()
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get plan by ID."""
        return self.db.query(Plan).filter(
            Plan.plan_id == plan_id,
            Plan.is_active == True
        ).first()
    
    async def get_plan_by_uuid(self, plan_uuid: UUID) -> Optional[Plan]:
        """Get plan by UUID."""
        return self.db.query(Plan).filter(
            Plan.id == plan_uuid,
            Plan.is_active == True
        ).first()
    
    async def list_plans(self, include_hidden: bool = False) -> List[Plan]:
        """List all active plans."""
        query = self.db.query(Plan).filter(Plan.is_active == True)
        
        if not include_hidden:
            query = query.filter(Plan.is_public == True)
        
        return query.order_by(Plan.display_order).all()
    
    async def calculate_subscription_price(
        self,
        plan_id: str,
        quantity: int = 1,
        coupon_code: str = None,
        interval: str = "monthly"
    ) -> Dict:
        """
        Calculate price for a subscription.
        
        Returns:
            Dict with price breakdown
        """
        plan = await self.get_plan(plan_id)
        
        if not plan:
            raise PricingError(f"Plan {plan_id} not found")
        
        base_price = plan.price * quantity
        
        # Apply coupon if provided
        discount = 0
        if coupon_code:
            discount = await self._apply_coupon(coupon_code, base_price)
        
        # Apply interval multiplier
        if interval == "yearly":
            base_price *= 10  # 2 months free
        elif interval == "quarterly":
            base_price *= 3
        
        subtotal = base_price - discount
        tax = subtotal * settings.TAX_RATE
        total = subtotal + tax
        
        return {
            "plan": plan.to_dict(),
            "quantity": quantity,
            "base_price": base_price,
            "discount": discount,
            "subtotal": subtotal,
            "tax": tax,
            "tax_rate": settings.TAX_RATE,
            "total": total,
            "currency": settings.CURRENCY,
            "interval": interval
        }
    
    async def calculate_proration(
        self,
        subscription_id: UUID,
        new_plan_id: str,
        effective_date: datetime = None
    ) -> Dict:
        """
        Calculate prorated charges for plan change.
        
        Args:
            subscription_id: Current subscription
            new_plan_id: New plan ID
            effective_date: When change takes effect
            
        Returns:
            Proration calculation
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription:
            raise PricingError(f"Subscription {subscription_id} not found")
        
        current_plan = await self.get_plan_by_uuid(subscription.plan_id)
        new_plan = await self.get_plan(new_plan_id)
        
        if not new_plan:
            raise PricingError(f"Plan {new_plan_id} not found")
        
        if not effective_date:
            effective_date = datetime.utcnow()
        
        # Calculate days remaining in current period
        period_end = subscription.current_period_end
        days_remaining = (period_end - effective_date).days
        total_days = (period_end - subscription.current_period_start).days
        
        # Calculate unused portion of current plan
        current_daily_rate = current_plan.price / total_days
        unused_credit = current_daily_rate * days_remaining
        
        # Calculate cost of new plan for remaining days
        new_daily_rate = new_plan.price / total_days
        new_cost = new_daily_rate * days_remaining
        
        # Difference to charge
        proration_amount = new_cost - unused_credit
        
        return {
            "subscription_id": str(subscription_id),
            "current_plan": current_plan.to_dict(),
            "new_plan": new_plan.to_dict(),
            "effective_date": effective_date.isoformat(),
            "days_remaining": days_remaining,
            "unused_credit": unused_credit,
            "new_plan_cost": new_cost,
            "proration_amount": proration_amount,
            "currency": settings.CURRENCY
        }
    
    async def calculate_overage_charges(
        self,
        tenant_id: UUID,
        subscription_id: UUID,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict]:
        """Calculate overage charges for a period."""
        from .metering import UsageMeteringService
        
        metering = UsageMeteringService(self.db)
        usage = await metering.get_usage_summary(tenant_id, period_start, period_end)
        
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription or not subscription.plan:
            return []
        
        plan_limits = subscription.plan.limits or {}
        overage_charges = []
        
        for metric_name, metric_usage in usage.items():
            limit = plan_limits.get(metric_name, 0)
            total_used = metric_usage["total"]
            
            if total_used > limit:
                overage = total_used - limit
                
                # Get overage rate (could be from plan metadata)
                overage_rate = 0.1  # Default KES 0.10 per unit
                
                charge = {
                    "metric": metric_name,
                    "usage": total_used,
                    "limit": limit,
                    "overage": overage,
                    "rate": overage_rate,
                    "amount": overage * overage_rate,
                    "currency": settings.CURRENCY
                }
                overage_charges.append(charge)
        
        return overage_charges
    
    async def _apply_coupon(self, coupon_code: str, amount: float) -> float:
        """Apply coupon discount."""
        # TODO: Implement coupon logic
        # This would check database for valid coupons
        return 0
    
    async def validate_coupon(self, coupon_code: str) -> Dict:
        """Validate a coupon code."""
        # TODO: Implement coupon validation
        return {
            "valid": False,
            "message": "Coupon system not implemented"
        }