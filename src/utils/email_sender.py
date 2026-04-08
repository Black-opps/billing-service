"""
Email sending utility for invoices and notifications.
"""
import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class EmailSender:
    """Send emails for billing notifications."""
    
    async def send_invoice_email(self, tenant_id: UUID, invoice: dict):
        """
        Send invoice email to tenant.
        
        Args:
            tenant_id: Tenant UUID
            invoice: Invoice data
        """
        try:
            # TODO: Implement actual email sending
            # This would use SMTP or SendGrid
            logger.info(f"Sending invoice email to tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}")
    
    async def send_payment_receipt(self, tenant_id: UUID, invoice: dict):
        """
        Send payment receipt email.
        
        Args:
            tenant_id: Tenant UUID
            invoice: Invoice data
        """
        try:
            logger.info(f"Sending payment receipt to tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to send payment receipt: {e}")
    
    async def send_overdue_reminder(self, tenant_id: UUID, invoice: dict):
        """
        Send overdue invoice reminder.
        
        Args:
            tenant_id: Tenant UUID
            invoice: Invoice data
        """
        try:
            logger.info(f"Sending overdue reminder to tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to send overdue reminder: {e}")