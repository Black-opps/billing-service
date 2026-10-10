# billing-service/src/core/dependencies.py
import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..security.jwks import decode_token

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)  # Don't auto-raise, we'll handle it


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Get current tenant from JWT token.

    Validates the token and extracts the tenant_id.
    Raises 401 if token is invalid or missing.
    """
    # Check if credentials were provided
    if not credentials:
        logger.warning("❌ No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Check if token is empty
    if not token or token.strip() == "":
        logger.warning("❌ Empty token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - empty token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate the token
    logger.info(f"🔍 Validating token for get_current_tenant: {token[:20]}...")
    payload = await decode_token(token)

    # CRITICAL: Reject invalid tokens
    if not payload:
        logger.error("❌ Token validation failed in get_current_tenant")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log the entire payload for debugging
    logger.info(f"📋 Full payload keys: {list(payload.keys())}")
    logger.info(f"📋 Full payload: {payload}")

    # Try multiple ways to get tenant_id
    tenant_id = payload.get("tenant_id")

    # If not found, try other common names
    if not tenant_id:
        tenant_id = payload.get("tenantId")
    if not tenant_id:
        tenant_id = payload.get("tenant")
    if not tenant_id:
        tenant_id = payload.get("tenantID")

    # If still not found, check if it's in the sub claim (some tokens use sub as tenant)
    if not tenant_id:
        # Check if sub is a UUID (tenant IDs are UUIDs)
        import re

        sub = payload.get("sub")
        if sub and re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            sub,
            re.IGNORECASE,
        ):
            tenant_id = sub
            logger.info(f"✅ Using 'sub' as tenant_id: {tenant_id}")

    if not tenant_id:
        logger.error(
            f"❌ No tenant_id found in token payload. Available keys: {list(payload.keys())}"
        )
        # For debugging, return a default tenant in development
        if getattr(settings, "ENVIRONMENT", "development") == "development":
            logger.warning("⚠️ DEVELOPMENT: Using default tenant_id 'dev-tenant'")
            return "dev-tenant"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ Tenant validated: {tenant_id}")
    return tenant_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Get current user from JWT token.

    Validates the token and returns the full user payload.
    Raises 401 if token is invalid or missing.
    """
    # Check if credentials were provided
    if not credentials:
        logger.warning("❌ No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Check if token is empty
    if not token or token.strip() == "":
        logger.warning("❌ Empty token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - empty token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate the token
    logger.info(f"🔍 Validating token for get_current_user: {token[:20]}...")
    payload = await decode_token(token)

    # CRITICAL: Reject invalid tokens
    if not payload:
        logger.error("❌ Token validation failed in get_current_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ User validated: {payload.get('email')}")
    return payload


async def require_permission(permission: str):
    """
    Dependency factory for checking user permissions.

    Args:
        permission: The required permission string (e.g., "admin:plans")

    Returns:
        A dependency function that checks if the user has the required permission
    """

    async def permission_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> str:
        """
        Check if user has required permission.

        Validates the token and checks permissions.
        Raises 401 if token is invalid, 403 if permissions are insufficient.
        """
        # Check if credentials were provided
        if not credentials:
            logger.warning("❌ No credentials provided for permission check")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated - missing token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        # Check if token is empty
        if not token or token.strip() == "":
            logger.warning("❌ Empty token provided for permission check")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated - empty token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate the token
        logger.info(
            f"🔍 Validating token for permission '{permission}': {token[:20]}..."
        )
        payload = await decode_token(token)

        # CRITICAL: Reject invalid tokens
        if not payload:
            logger.error(f"❌ Token validation failed for permission '{permission}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated - invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user has the required permission
        user_permissions = payload.get("permissions", [])
        user_role = payload.get("role")

        # Admin role has all permissions
        if user_role == "admin":
            logger.info(
                f"✅ Admin user {payload.get('email')} granted permission '{permission}'"
            )
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Tenant ID not found in token",
                )
            return tenant_id

        # Check specific permission
        if permission not in user_permissions:
            logger.warning(
                f"❌ User {payload.get('email')} lacks permission '{permission}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )

        # Return tenant_id for use in the endpoint
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant ID not found in token",
            )

        logger.info(f"✅ Permission '{permission}' granted for tenant {tenant_id}")
        return tenant_id

    return permission_checker
