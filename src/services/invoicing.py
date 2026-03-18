"""
Invoicing service.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from uuid import UUID
import random
import string

from ..models.invoice import Invoice, InvoiceStatus, InvoiceItem
from ..models.subscription import Subscription
from ..models.usage import UsageRecord
from ..services.metering import UsageMeteringService
from ..utils.pdf_generator import PDFGenerator
from ..utils.email_sender import EmailSender
from ..core.exceptions import InvoicingError
from ..core.config import settings

logger = logging.getLogger(__name__)


class InvoicingService:
    """Service for generating and managing invoices."""
    
    def __init__(self, db: Session):
        self.db = db
        self.metering = UsageMeteringService(db)
        self.pdf_generator = PDFGenerator()
        self.email_sender = EmailSender()
    
    def _generate_invoice_number(self) -> str:
        """Generate a unique invoice number."""
        prefix = "INV"
        date_part = datetime.utcnow().strftime("%Y%m")
        random_part = ''.join(random.choices(string.digits, k=6))
        
        invoice_number = f"{prefix}-{datePart}-{randomPart}"
        
        # Ensure uniqueness
        while self.db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number
        ).first():
            random_part = ''.join(random.choices(string.digits, k=6))
            invoice_number = f"{prefix}-{datePart}-{randomPart}"
        
        return invoice_number
    
    async def generate_invoice(
        self,
        tenant_id: UUID,
        subscription_id: UUID = None,
        period_start: datetime = None,
        period_end: datetime = None,
        items: List[Dict] = None
    ) -> Invoice:
        """
        Generate an invoice.
        
        Args:
            tenant_id: Tenant UUID
            subscription_id: Associated subscription
            period_start: Start of billing period
            period_end: End of billing period
            items: Line items (if None, generate from subscription)
            
        Returns:
            Generated invoice
        """
        if not period_start:
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if not period_end:
            # End of month
            next_month = period_start.replace(day=28) + timedelta(days=4)
            period_end = next_month - timedelta(days=next_month.day)
        
        # Create invoice
        invoice = Invoice(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            invoice_number=self._generate_invoice_number(),
            status=InvoiceStatus.DRAFT,
            period_start=period_start,
            period_end=period_end,
            issue_date=datetime.utcnow().date(),
            due_date=(datetime.utcnow() + timedelta(days=settings.INVOICE_DUE_DAYS)).date(),
            currency=settings.CURRENCY,
            items=[]
        )
        
        self.db.add(invoice)
        self.db.flush()
        
        # Generate items
        if items:
            for item_data in items:
                await self._add_item(invoice.id, item_data)
        elif subscription_id:
            await self._generate_subscription_items(invoice.id, subscription_id)
        
        # Calculate totals
        await self._calculate_totals(invoice.id)
        
        # Refresh invoice
        self.db.refresh(invoice)
        
        logger.info(f"Generated invoice {invoice.invoice_number} for tenant {tenant_id}")
        
        return invoice
    
    async def _generate_subscription_items(self, invoice_id: UUID, subscription_id: UUID):
        """Generate invoice items from subscription."""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not subscription:
            return
        
        # Add subscription fee
        await self._add_item(invoice_id, {
            "description": f"Subscription - {subscription.plan.name}",
            "quantity": 1,
            "unit_price": subscription.unit_price,
            "item_type": "subscription",
            "item_id": str(subscription_id)
        })
        
        # Calculate and add overages
        await self._add_overage_items(invoice_id, subscription)
    
    async def _add_overage_items(self, invoice_id: UUID, subscription: Subscription):
        """Add overage charges to invoice."""
        # Get usage for period
        usage = await self.metering.get_usage_summary(
            tenant_id=subscription.tenant_id,
            start_date=subscription.current_period_start,
            end_date=subscription.current_period_end
        )
        
        plan_limits = subscription.plan.limits or {}
        
        for metric_name, metric_usage in usage.items():
            limit = plan_limits.get(metric_name, 0)
            total_used = metric_usage["total"]
            
            if total_used > limit:
                overage = total_used - limit
                
                # TODO: Get overage pricing from plan
                overage_price = 0.1  # Example: KES 0.10 per extra transaction
                
                await self._add_item(invoice_id, {
                    "description": f"Overage - {metric_name} ({overage} units)",
                    "quantity": overage,
                    "unit_price": overage_price,
                    "item_type": "overage",
                    "item_id": metric_name
                })
    
    async def _add_item(self, invoice_id: UUID, item_data: Dict):
        """Add an item to an invoice."""
        quantity = item_data.get("quantity", 1)
        unit_price = item_data.get("unit_price", 0)
        amount = quantity * unit_price
        tax_amount = amount * settings.TAX_RATE
        
        item = InvoiceItem(
            invoice_id=invoice_id,
            description=item_data["description"],
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
            tax_rate=settings.TAX_RATE,
            tax_amount=tax_amount,
            item_type=item_data.get("item_type"),
            item_id=item_data.get("item_id"),
            metadata=item_data.get("metadata", {})
        )
        
        self.db.add(item)
        
        return item
    
    async def _calculate_totals(self, invoice_id: UUID):
        """Calculate invoice totals."""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            return
        
        items = self.db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()
        
        subtotal = sum(item.amount for item in items)
        tax_total = sum(item.tax_amount for item in items)
        total = subtotal + tax_total
        
        invoice.subtotal = subtotal
        invoice.tax_total = tax_total
        invoice.total = total
        invoice.amount_due = total
        
        self.db.commit()
    
    async def finalize_invoice(self, invoice_id: UUID) -> Invoice:
        """Finalize a draft invoice."""
        invoice = self.db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.status == InvoiceStatus.DRAFT
        ).first()
        
        if not invoice:
            raise InvoicingError(f"Draft invoice {invoice_id} not found")
        
        # Generate PDF
        pdf_url = await self.pdf_generator.generate_invoice_pdf(invoice)
        invoice.pdf_url = pdf_url
        
        # Update status
        invoice.status = InvoiceStatus.PENDING
        
        self.db.commit()
        
        logger.info(f"Finalized invoice {invoice.invoice_number}")
        
        return invoice
    
    async def send_invoice_notification(self, invoice_id: UUID):
        """Send invoice notification to tenant."""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            return
        
        # Mark as sent
        invoice.status = InvoiceStatus.SENT
        self.db.commit()
        
        # Send email
        await self.email_sender.send_invoice_email(
            tenant_id=invoice.tenant_id,
            invoice=invoice.to_dict()
        )
        
        logger.info(f"Sent invoice {invoice.invoice_number} to tenant {invoice.tenant_id}")
    
    async def mark_as_paid(
        self,
        invoice_id: UUID,
        payment_method: str,
        transaction_id: str = None
    ) -> Invoice:
        """Mark an invoice as paid."""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            raise InvoicingError(f"Invoice {invoice_id} not found")
        
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        invoice.payment_method = payment_method
        invoice.mpesa_transaction_id = transaction_id
        invoice.amount_paid = invoice.total
        invoice.amount_due = 0
        
        self.db.commit()
        
        logger.info(f"Invoice {invoice.invoice_number} marked as paid")
        
        # Send receipt
        await self.email_sender.send_payment_receipt(
            tenant_id=invoice.tenant_id,
            invoice=invoice.to_dict()
        )
        
        return invoice
    
    async def void_invoice(self, invoice_id: UUID, reason: str = None) -> Invoice:
        """Void an invoice."""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            raise InvoicingError(f"Invoice {invoice_id} not found")
        
        if invoice.status == InvoiceStatus.PAID:
            raise InvoicingError("Cannot void a paid invoice")
        
        invoice.status = InvoiceStatus.VOID
        invoice.metadata["void_reason"] = reason
        invoice.metadata["voided_at"] = datetime.utcnow().isoformat()
        
        self.db.commit()
        
        logger.info(f"Invoice {invoice.invoice_number} voided")
        
        return invoice
    
    async def get_tenant_invoices(
        self,
        tenant_id: UUID,
        status: Optional[InvoiceStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Invoice]:
        """Get invoices for a tenant."""
        query = self.db.query(Invoice).filter(Invoice.tenant_id == tenant_id)
        
        if status:
            query = query.filter(Invoice.status == status)
        
        return query.order_by(Invoice.created_at.desc()).limit(limit).offset(offset).all()
    
    async def get_outstanding_invoices(self, tenant_id: UUID) -> List[Invoice]:
        """Get all outstanding (unpaid) invoices for a tenant."""
        return self.db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.SENT, InvoiceStatus.OVERDUE])
        ).all()
    
    async def check_overdue_invoices(self):
        """Check for overdue invoices and update status."""
        overdue = self.db.query(Invoice).filter(
            Invoice.due_date < datetime.utcnow().date(),
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.SENT])
        ).all()
        
        for invoice in overdue:
            invoice.status = InvoiceStatus.OVERDUE
            logger.info(f"Invoice {invoice.invoice_number} marked as overdue")
            
            # Send reminder
            await self.email_sender.send_overdue_reminder(
                tenant_id=invoice.tenant_id,
                invoice=invoice.to_dict()
            )
        
        self.db.commit()