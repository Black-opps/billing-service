# billing-service/src/api/test_sdk.py
"""
Test endpoints for SDK validation.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

# Use the billing service's existing dependencies (which work)
from ..core.dependencies import get_current_tenant, get_current_user

router = APIRouter(prefix="/test-sdk", tags=["SDK Test"])


@router.get("/tenant")
async def test_tenant(
    tenant_id: str = Depends(get_current_tenant), user: dict = Depends(get_current_user)
):
    """
    Test tenant extraction from JWT using billing service dependencies.
    """
    return {
        "success": True,
        "tenant_id": tenant_id,
        "user_email": user.get("email"),
        "user_role": user.get("role"),
        "message": "Tenant extraction working!",
    }


@router.get("/user")
async def test_user(user: dict = Depends(get_current_user)):
    """
    Test user extraction from JWT using billing service dependencies.
    """
    return {
        "success": True,
        "user": {
            "id": user.get("sub"),
            "email": user.get("email"),
            "role": user.get("role"),
            "tenant_id": user.get("tenant_id"),
        },
        "message": "User extraction working!",
    }


@router.get("/validate-tenant/{resource_tenant_id}")
async def test_tenant_validation(
    resource_tenant_id: str, tenant_id: str = Depends(get_current_tenant)
):
    """
    Test tenant validation.
    """
    # Check if the user has access to the requested tenant
    if tenant_id != resource_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to tenant: {resource_tenant_id}",
        )

    return {
        "success": True,
        "message": f"Access granted to tenant: {resource_tenant_id}",
        "tenant_id": resource_tenant_id,
    }


@router.get("/debug-token")
async def debug_token(request: Request, user: dict = Depends(get_current_user)):
    """
    Debug endpoint to see what's in the token.
    """
    return {
        "user": user,
        "headers": dict(request.headers),
    }
