from pydantic import BaseModel
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime, date
from enum import Enum


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class InvoiceItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    amount: float
    tax_rate: float = 0.16
    tax_amount: float
    item_type: Optional[str] = None
    item_id: Optional[str] = None


class InvoiceCreate(BaseModel):
    tenant_id: UUID
    subscription_id: Optional[UUID] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    items: Optional[List[Dict]] = None


class InvoiceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    subscription_id: Optional[UUID]
    invoice_number: str
    status: InvoiceStatus
    period_start: datetime
    period_end: datetime
    issue_date: date
    due_date: date
    subtotal: float
    tax_total: float
    total: float
    amount_due: float
    currency: str
    items: List
    paid_at: Optional[datetime] = None
    mpesa_transaction_id: Optional[str] = None
    pdf_url: Optional[str] = None
    created_at: datetime
    is_overdue: bool
    days_overdue: int

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    id: UUID
    invoice_number: str
    status: InvoiceStatus
    total: float
    currency: str
    due_date: date
    created_at: datetime


class InvoicePayment(BaseModel):
    method: str
    transaction_id: Optional[str] = None