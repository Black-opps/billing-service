"""
Billing cycle management service.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from uuid import UUID
import asyncio

from ..models.subscription import Subscription, SubscriptionStatus, BillingInterval
from ..models.invoice import Invoice, InvoiceStatus
from ..models.plan import Plan
from ..services.invoicing import InvoicingService
from ..services.metering import UsageMeteringService
from ..core.exceptions import BillingError
from ..core.database import db_session
from ..core.config import settings

logger = logging.getLogger(__name__)


class BillingCycleService:
    """Service for managing billing cycles."""
    
    def __init__(self, db: Session):
        self.db = db
        self.invoicing = InvoicingService(db)
        self.metering = UsageMeteringService(db)
    
    async def process_monthly_billing(self) -> dict:
        """
        Process monthly billing for all active subscriptions.
        Runs on the 1st of each month.
        """
        logger.info("Starting monthly billing cycle...")
        
        stats = {
            "processed": 0,
            "invoices_generated": 0,
            "invoices_failed": 0,
            "subscriptions_renewed": 0,
            "subscriptions_expired": 0
        }
        
        # Get all active subscriptions
        subscriptions = self.db.query(Subscription).filter(
            Subscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING
            ])
        ).all()
        
        for subscription in subscriptions:
            try:
                await self._process_subscription_billing(subscription)
                stats["processed"] += 1
                stats["invoices_generated"] += 1
            except Exception as e:
                logger.error(f"Failed to process subscription {subscription.id}: {e}")
                stats["invoices_failed"] += 1
        
        # Check for expired trials
        expired_trials = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.TRIALING,
            Subscription.trial_end < datetime.utcnow()
        ).all()
        
        for trial in expired_trials:
            trial.status = SubscriptionStatus.EXPIRED
            stats["subscriptions_expired"] += 1
        
        self.db.commit()
        
        logger.info(f"Monthly billing completed: {stats}")
        return stats
    
    async def _process_subscription_billing(self, subscription: Subscription):
        """Process billing for a single subscription."""
        
        # Check if subscription period has ended
        if subscription.current_period_end <= datetime.utcnow():
            await self._renew_subscription(subscription)
        
        # Generate invoice for current period if not already generated
        existing = self.db.query(Invoice).filter(
            Invoice.subscription_id == subscription.id,
            Invoice.period_start == subscription.current_period_start
        ).first()
        
        if not existing:
            invoice = await self.invoicing.generate_invoice(
                tenant_id=subscription.tenant_id,
                subscription_id=subscription.id,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end
            )
            
            # Send invoice notification
            await self.invoicing.send_invoice_notification(invoice.id)
    
    async def _renew_subscription(self, subscription: Subscription):
        """Renew a subscription for the next period."""
        
        # Calculate next period dates
        if subscription.billing_cycle == BillingInterval.MONTHLY:
            next_start = subscription.current_period_end
            next_end = next_start + timedelta(days=30)
        elif subscription.billing_cycle == BillingInterval.QUARTERLY:
            next_start = subscription.current_period_end
            next_end = next_start + timedelta(days=90)
        elif subscription.billing_cycle == BillingInterval.YEARLY:
            next_start = subscription.current_period_end
            next_end = next_start + timedelta(days=365)
        
        # Update subscription
        subscription.current_period_start = next_start
        subscription.current_period_end = next_end
        subscription.status = SubscriptionStatus.ACTIVE
        
        logger.info(f"Renewed subscription {subscription.id} until {next_end}")
    
    async def check_subscription_status(self, subscription_id: UUID) -> dict:
        """Check subscription status and take action if needed."""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription:
            raise BillingError(f"Subscription {subscription_id} not found")
        
        status_info = {
            "subscription_id": str(subscription.id),
            "status": subscription.status.value,
            "current_period_end": subscription.current_period_end,
            "days_remaining": (subscription.current_period_end - datetime.utcnow()).days,
            "actions_needed": []
        }
        
        # Check if nearing renewal
        if status_info["days_remaining"] <= 7 and subscription.auto_renew:
            status_info["actions_needed"].append("auto_renewal_soon")
        
        # Check if past due
        if subscription.status == SubscriptionStatus.PAST_DUE:
            status_info["actions_needed"].append("payment_overdue")
        
        # Check if trial ending
        if subscription.trial_end and subscription.trial_end > datetime.utcnow():
            trial_days = (subscription.trial_end - datetime.utcnow()).days
            if trial_days <= 3:
                status_info["actions_needed"].append("trial_ending_soon")
        
        return status_info
    
    async def cancel_subscription(
        self,
        subscription_id: UUID,
        cancel_immediately: bool = False
    ) -> Subscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription UUID
            cancel_immediately: If True, cancel now; if False, cancel at period end
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription:
            raise BillingError(f"Subscription {subscription_id} not found")
        
        if cancel_immediately:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.utcnow()
            logger.info(f"Immediately canceled subscription {subscription_id}")
        else:
            subscription.cancel_at_period_end = True
            logger.info(f"Subscription {subscription_id} will cancel at period end")
        
        self.db.commit()
        return subscription
    
    async def reactivate_subscription(self, subscription_id: UUID) -> Subscription:
        """Reactivate a canceled subscription."""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.status == SubscriptionStatus.CANCELED
        ).first()
        
        if not subscription:
            raise BillingError(f"Canceled subscription {subscription_id} not found")
        
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        
        self.db.commit()
        logger.info(f"Reactivated subscription {subscription_id}")
        
        return subscription
    
    async def handle_failed_payment(self, subscription_id: UUID):
        """Handle a failed payment for a subscription."""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription:
            return
        
        # Update status to past due
        subscription.status = SubscriptionStatus.PAST_DUE
        
        # Create grace period record
        # TODO: Add grace period tracking
        
        logger.warning(f"Payment failed for subscription {subscription_id}")
        
        # Send notification
        # await self.notification_service.send_payment_failed(subscription.tenant_id)
        
        self.db.commit()
    
    async def process_grace_periods(self):
        """Process subscriptions in grace period."""
        grace_end = datetime.utcnow() - timedelta(days=settings.GRACE_PERIOD_DAYS)
        
        overdue = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.PAST_DUE,
            Subscription.updated_at < grace_end
        ).all()
        
        for subscription in overdue:
            subscription.status = SubscriptionStatus.EXPIRED
            logger.info(f"Subscription {subscription.id} expired after grace period")
        
        self.db.commit()