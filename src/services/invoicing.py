"""
Invoicing service - generates invoices from usage data.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.invoice import Invoice, InvoiceItem
from ..models.subscription import Subscription
from ..models.usage import Usage
from ..services.pricing import PricingService

logger = logging.getLogger(__name__)


class InvoicingService:
    """Service for generating and managing invoices"""

    def __init__(self, db: Session):
        self.db = db
        self.pricing = PricingService(db)

    async def generate_monthly_invoice(
        self, tenant_id: str, period: Optional[str] = None
    ) -> Invoice:
        """
        Generate a monthly invoice for a tenant.
        Called at end of billing cycle.
        """

        if not period:
            period = datetime.utcnow().strftime("%Y-%m")

        logger.info(f"📄 Generating invoice for {tenant_id} - {period}")

        # Get subscription
        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id, Subscription.status == "active"
            )
            .first()
        )

        plan_id = subscription.plan_id if subscription else "free"

        # Get usage for the period
        usage = (
            self.db.query(Usage)
            .filter(Usage.tenant_id == tenant_id, Usage.billing_period == period)
            .first()
        )

        usage_data = {
            "transactions_processed": usage.transactions_processed if usage else 0,
            "historical_months_imported": (
                usage.historical_months_imported if usage else 0
            ),
            "period": period,
        }

        # Calculate invoice
        invoice_calc = self.pricing.calculate_monthly_invoice(
            tenant_id=tenant_id, usage=usage_data, plan_id=plan_id
        )

        # Create invoice
        invoice = Invoice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            subscription_id=subscription.id if subscription else None,
            invoice_number=self._generate_invoice_number(tenant_id, period),
            amount=invoice_calc["total"],
            currency=invoice_calc["currency"],
            status="pending",
            period_start=datetime.strptime(period, "%Y-%m").replace(day=1),
            period_end=datetime.strptime(period, "%Y-%m").replace(
                day=28, hour=23, minute=59, second=59
            ),
            due_date=datetime.utcnow() + timedelta(days=7),
            metadata={
                "plan": plan_id,
                "period": period,
                "usage": usage_data,
            },
            created_at=datetime.utcnow(),
        )
        self.db.add(invoice)
        self.db.flush()

        # Create invoice items
        for item in invoice_calc["items"]:
            invoice_item = InvoiceItem(
                id=str(uuid.uuid4()),
                invoice_id=invoice.id,
                description=item["description"],
                amount=item["amount"],
                type=item["type"],
                details=item.get("details", {}),
                created_at=datetime.utcnow(),
            )
            self.db.add(invoice_item)

        self.db.commit()
        self.db.refresh(invoice)

        logger.info(
            f"✅ Invoice {invoice.invoice_number} generated: KES {invoice.amount}"
        )
        return invoice

    def _generate_invoice_number(self, tenant_id: str, period: str) -> str:
        """Generate a unique invoice number"""
        # Format: INV-{tenant_short}-{period}
        tenant_short = tenant_id[:8].upper()
        return f"INV-{tenant_short}-{period.replace('-', '')}"

    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID"""
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    async def get_tenant_invoices(
        self, tenant_id: str, status: Optional[str] = None, limit: int = 50
    ) -> List[Invoice]:
        """Get all invoices for a tenant"""

        query = self.db.query(Invoice).filter(Invoice.tenant_id == tenant_id)

        if status:
            query = query.filter(Invoice.status == status)

        return query.order_by(Invoice.created_at.desc()).limit(limit).all()

    async def mark_paid(self, invoice_id: str, payment_id: str) -> bool:
        """Mark an invoice as paid"""

        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            return False

        invoice.status = "paid"
        invoice.paid_at = datetime.utcnow()
        invoice.payment_id = payment_id
        self.db.commit()

        logger.info(f"✅ Invoice {invoice.invoice_number} marked as paid")
        return True

    async def get_outstanding_balance(self, tenant_id: str) -> float:
        """Get total outstanding balance for a tenant"""

        invoices = await self.get_tenant_invoices(tenant_id=tenant_id, status="pending")

        return sum(inv.amount for inv in invoices)
