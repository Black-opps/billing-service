"""
Billing service custom exceptions.
"""

class BillingError(Exception):
    """Base exception for billing service."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PricingError(BillingError):
    """Exception for pricing-related errors."""
    pass


class SubscriptionError(BillingError):
    """Exception for subscription-related errors."""
    pass


class UsageError(BillingError):
    """Exception for usage metering errors."""
    pass


class InvoiceError(BillingError):
    """Exception for invoice generation errors."""
    pass


# Aliases for compatibility with different naming conventions
InvoicingError = InvoiceError
MeteringError = UsageError
BillingCycleError = SubscriptionError
PricingServiceError = PricingError


class PlanNotFoundError(PricingError):
    """Exception when a plan is not found."""
    def __init__(self, plan_id: str):
        super().__init__(f"Plan '{plan_id}' not found", 404)


class SubscriptionNotFoundError(SubscriptionError):
    """Exception when a subscription is not found."""
    def __init__(self, subscription_id: str):
        super().__init__(f"Subscription '{subscription_id}' not found", 404)


class TenantNotFoundError(BillingError):
    """Exception when a tenant is not found."""
    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant '{tenant_id}' not found", 404)


class UsageLimitExceededError(UsageError):
    """Exception when usage exceeds plan limits."""
    def __init__(self, metric: str, limit: int, current: int):
        super().__init__(
            f"Usage limit exceeded for '{metric}': {current}/{limit}", 
            429
        )


class InvoiceGenerationError(InvoiceError):
    """Exception when invoice generation fails."""
    pass