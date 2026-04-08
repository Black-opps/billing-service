"""
Security utilities for billing service.
These will be replaced by auth-service integration later.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os

security = HTTPBearer()

# Mock user for development
MOCK_USER = {
    "id": "mock-user-123",
    "tenant_id": "7305d298-80c8-419e-bc9f-c4f9a37c1fe3",
    "email": "admin@acme.com",
    "role": "admin"
}


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Get current user from token (mock for development)."""
    # In development, return mock user
    if os.getenv("ENVIRONMENT", "development") == "development":
        return MOCK_USER
    
    # In production, validate token with auth-service
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # TODO: Call auth-service to validate token
    return MOCK_USER


async def get_current_tenant(user: dict = Depends(get_current_user)) -> str:
    """Get current tenant ID from user context."""
    return user.get("tenant_id")


def require_permission(permission: str):
    """Dependency to check if user has specific permission."""
    async def permission_checker(user: dict = Depends(get_current_user)):
        # In development, allow all
        if os.getenv("ENVIRONMENT", "development") == "development":
            return user
        
        # TODO: Check permissions with auth-service
        return user
    return permission_checker