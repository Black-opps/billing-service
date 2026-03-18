"""
Invoice models.
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, JSON, DateTime, Enum, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta
import enum

from ..core.database import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice status."""
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"
    REFUNDED = "refunded"


class Invoice(Base):
    """Invoice model."""
    
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    
    # Invoice identification
    invoice_number = Column(String(50), unique=True, nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    
    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    issue_date = Column(Date, default=datetime.utcnow().date)
    due_date = Column(Date, nullable=False)
    
    # Amounts
    subtotal = Column(Float, nullable=False, default=0)
    tax_total = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)
    amount_paid = Column(Float, nullable=False, default=0)
    amount_due = Column(Float, nullable=False, default=0)
    currency = Column(String(3), default="KES")
    
    # Items
    items = Column(JSON, nullable=False, default=list)  # List of invoice items
    
    # Payment
    payment_method = Column(String(50), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    mpesa_transaction_id = Column(String(100), nullable=True)
    
    # PDF
    pdf_url = Column(String(500), nullable=True)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    
    def __repr__(self):
        return f"<Invoice {self.invoice_number}: {self.total} {self.currency}>"
    
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if self.status == InvoiceStatus.PAID:
            return False
        return datetime.utcnow().date() > self.due_date
    
    @property
    def days_overdue(self) -> int:
        """Get days overdue."""
        if not self.is_overdue:
            return 0
        delta = datetime.utcnow().date() - self.due_date
        return delta.days
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "invoice_number": self.invoice_number,
            "status": self.status.value,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "subtotal": self.subtotal,
            "tax_total": self.tax_total,
            "total": self.total,
            "amount_due": self.amount_due,
            "currency": self.currency,
            "items": self.items,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "mpesa_transaction_id": self.mpesa_transaction_id,
            "pdf_url": self.pdf_url,
            "is_overdue": self.is_overdue,
            "days_overdue": self.days_overdue
        }


class InvoiceItem(Base):
    """Individual line items on an invoice."""
    
    __tablename__ = "invoice_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    
    # Item details
    description = Column(String(500), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    
    # Tax
    tax_rate = Column(Float, default=0.16)
    tax_amount = Column(Float, default=0)
    
    # Metadata
    item_type = Column(String(50))  # 'subscription', 'addon', 'overage', 'credit'
    item_id = Column(String(100))  # Reference ID
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)