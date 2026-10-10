# billing-service/src/core/security.py
import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..security.jwks import decode_token

logger = logging.getLogger(__name__)

# Use auto_error=False to handle missing tokens ourselves
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    Get current user from JWT token.

    Validates the JWT token and returns the user payload.
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

    # Log token validation attempt (only first 20 chars)
    token_preview = token[:20] + "..." if len(token) > 20 else token
    logger.info(f"🔍 Validating token in security.py: {token_preview}")

    # Validate the token
    payload = await decode_token(token)

    # CRITICAL: Reject invalid tokens
    if not payload:
        logger.error(f"❌ Invalid token in security.py: {token_preview}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ Token validated for user: {payload.get('email')}")
    return payload


async def get_current_tenant(user: dict = Depends(get_current_user)) -> str:
    """
    Get current tenant ID from validated user context.
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        logger.error(f"❌ No tenant_id in token for user: {user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ Tenant validated: {tenant_id}")
    return tenant_id


def require_permission(permission: str):
    """
    Dependency to check if user has specific permission.
    """

    async def permission_checker(user: dict = Depends(get_current_user)) -> dict:
        # Check if user has the required permission
        user_permissions = user.get("permissions", [])
        user_role = user.get("role")

        # Admin role has all permissions
        if user_role == "admin":
            logger.info(
                f"✅ Admin user {user.get('email')} granted permission '{permission}'"
            )
            return user

        # Check specific permission
        if permission not in user_permissions:
            logger.warning(
                f"❌ User {user.get('email')} lacks permission '{permission}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )

        logger.info(
            f"✅ Permission '{permission}' granted for user {user.get('email')}"
        )
        return user

    return permission_checker
