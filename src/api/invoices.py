"""
Invoice management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ..core.database import get_db
from ..core.security import get_current_user, require_permission
from ..services.invoicing import InvoicingService
from ..models.user import User
from ..models.invoice import Invoice, InvoiceStatus
from ..schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceListResponse,
    InvoicePayment
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("create:invoices"))
):
    """Create a new invoice."""
    invoicing = InvoicingService(db)
    
    try:
        invoice = await invoicing.generate_invoice(
            tenant_id=invoice_data.tenant_id,
            subscription_id=invoice_data.subscription_id,
            period_start=invoice_data.period_start,
            period_end=invoice_data.period_end,
            items=invoice_data.items
        )
        
        return invoice
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenant/{tenant_id}", response_model=List[InvoiceListResponse])
async def get_tenant_invoices(
    tenant_id: UUID,
    status: Optional[InvoiceStatus] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all invoices for a tenant."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    invoicing = InvoicingService(db)
    
    invoices = await invoicing.get_tenant_invoices(
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return invoices


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get invoice details."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.tenant_id != invoice.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return invoice


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download invoice as PDF."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access
    if current_user.tenant_id != invoice.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not invoice.pdf_url:
        raise HTTPException(status_code=404, detail="PDF not generated yet")
    
    return FileResponse(
        invoice.pdf_url,
        media_type="application/pdf",
        filename=f"invoice-{invoice.invoice_number}.pdf"
    )


@router.post("/{invoice_id}/finalize", response_model=InvoiceResponse)
async def finalize_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:invoices"))
):
    """Finalize a draft invoice."""
    invoicing = InvoicingService(db)
    
    try:
        invoice = await invoicing.finalize_invoice(invoice_id)
        return invoice
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("send:invoices"))
):
    """Send invoice to customer."""
    invoicing = InvoicingService(db)
    
    try:
        await invoicing.send_invoice_notification(invoice_id)
        return {"message": "Invoice sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: UUID,
    payment_data: InvoicePayment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark invoice as paid."""
    invoicing = InvoicingService(db)
    
    try:
        invoice = await invoicing.mark_as_paid(
            invoice_id=invoice_id,
            payment_method=payment_data.method,
            transaction_id=payment_data.transaction_id
        )
        
        return {
            "message": "Invoice marked as paid",
            "invoice_id": str(invoice_id),
            "invoice_number": invoice.invoice_number
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invoice_id}/void")
async def void_invoice(
    invoice_id: UUID,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage:invoices"))
):
    """Void an invoice."""
    invoicing = InvoicingService(db)
    
    try:
        invoice = await invoicing.void_invoice(invoice_id, reason)
        return {"message": "Invoice voided"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/outstanding")
async def get_outstanding_invoices(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get outstanding invoices for tenant."""
    # Check access
    if current_user.tenant_id != tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    
    invoicing = InvoicingService(db)
    
    invoices = await invoicing.get_outstanding_invoices(tenant_id)
    
    total_due = sum(inv.amount_due for inv in invoices)
    
    return {
        "tenant_id": str(tenant_id),
        "total_due": total_due,
        "count": len(invoices),
        "invoices": [inv.to_dict() for inv in invoices]
    }