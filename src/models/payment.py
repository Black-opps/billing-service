"""
Payment models.
"""
from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..core.database import Base


class PaymentStatus(str, enum.Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Payment methods."""
    MPESA_STK = "mpesa_stk"
    MPESA_B2C = "mpesa_b2c"
    MPESA_C2B = "mpesa_c2b"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"


class Payment(Base):
    """Payment model."""
    
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    
    # Payment details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="KES")
    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # M-PESA specific
    mpesa_receipt = Column(String(100), nullable=True, index=True)
    phone_number = Column(String(20), nullable=True)
    transaction_id = Column(String(100), unique=True, nullable=True)
    checkout_request_id = Column(String(100), nullable=True)
    
    # Result
    result_code = Column(String(20), nullable=True)
    result_description = Column(String(500), nullable=True)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment {self.amount} {self.currency} - {self.status.value}>"
    
    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == PaymentStatus.COMPLETED
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "invoice_id": str(self.invoice_id) if self.invoice_id else None,
            "amount": self.amount,
            "currency": self.currency,
            "method": self.method.value,
            "status": self.status.value,
            "mpesa_receipt": self.mpesa_receipt,
            "phone_number": self.phone_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class PaymentMethod(Base):
    """Stored payment methods for tenants."""
    
    __tablename__ = "payment_methods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Method details
    method = Column(Enum(PaymentMethod), nullable=False)
    is_default = Column(Boolean, default=False)
    
    # M-PESA details
    phone_number = Column(String(20), nullable=True)
    paybill_number = Column(String(20), nullable=True)
    account_reference = Column(String(50), nullable=True)
    
    # Billing details
    billing_email = Column(String(255), nullable=True)
    
    # Status
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "method": self.method.value,
            "is_default": self.is_default,
            "phone_number": self.phone_number,
            "is_verified": self.is_verified,
            "is_active": self.is_active
        }