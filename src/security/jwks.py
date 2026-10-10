# billing-service/src/security/jwks.py
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
)

from ..core.config import settings

logger = logging.getLogger(__name__)

# Cache for JWKS
_jwks_cache = None
_jwks_cache_time = None


async def get_jwks() -> Dict[str, Any]:
    """Fetch JWKS from auth service with caching."""
    global _jwks_cache, _jwks_cache_time

    # Cache for 1 hour
    if _jwks_cache and _jwks_cache_time and (time.time() - _jwks_cache_time) < 3600:
        return _jwks_cache

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            jwks_url = f"{settings.AUTH_SERVICE_URL}/.well-known/jwks.json"
            logger.info(f"Fetching JWKS from {jwks_url}")
            response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_time = time.time()
            logger.info(
                f"JWKS fetched successfully, {len(_jwks_cache.get('keys', []))} keys found"
            )
            return _jwks_cache
        except httpx.TimeoutException:
            logger.error("Timeout connecting to auth service for JWKS")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Auth service returned error {e.response.status_code}: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise


async def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT token.

    Returns the payload if valid, None otherwise.
    """
    # Log the token for debugging (only first 20 chars)
    token_preview = token[:20] + "..." if len(token) > 20 else token
    logger.info(f"🔍 decode_token called with token: {token_preview}")

    # Check if token is empty
    if not token or token.strip() == "":
        logger.error("❌ Empty token provided")
        return None

    # Check if token is a JWT (has 3 parts separated by dots)
    if token.count(".") != 2:
        logger.error(
            f"❌ Token is not a valid JWT format (expected 3 parts, got {token.count('.') + 1})"
        )
        return None

    try:
        # Get JWKS
        logger.info("📡 Fetching JWKS...")
        jwks = await get_jwks()
        logger.info(
            f"✅ JWKS fetched, keys: {[k.get('kid') for k in jwks.get('keys', [])]}"
        )

        # Get the key from JWKS
        try:
            headers = jwt.get_unverified_header(token)
            logger.info(f"Token header: {headers}")
        except InvalidTokenError as e:
            logger.error(f"❌ Invalid token format: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error parsing token header: {e}")
            return None

        kid = headers.get("kid")

        if not kid:
            logger.error("❌ No kid in token header")
            return None

        # Find the matching key in JWKS
        key_data = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                key_data = key
                break

        if not key_data:
            logger.error(f"❌ Key {kid} not found in JWKS")
            return None

        logger.info(f"✅ Found key {kid} in JWKS")

        # Construct the public key
        try:
            public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
            logger.info("✅ Public key constructed successfully")
        except Exception as e:
            logger.error(f"❌ Failed to construct public key: {e}")
            return None

        # Decode and verify the token
        # Since the auth service doesn't include 'iss' or 'aud' claims,
        # we only verify signature and expiration
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,  # Auth service doesn't include 'aud'
                    "verify_iss": False,  # Auth service doesn't include 'iss'
                },
            )

            logger.info(
                f"✅ Token validated successfully for user: {payload.get('email')}"
            )

            # Verify required claims exist (but don't reject if missing, just warn)
            required_claims = ["exp", "iat", "sub", "email", "tenant_id"]
            missing_claims = [
                claim for claim in required_claims if claim not in payload
            ]
            if missing_claims:
                logger.warning(f"⚠️ Missing claims: {missing_claims}")

            return payload

        except ExpiredSignatureError:
            logger.error("❌ Token has expired")
            return None
        except InvalidSignatureError:
            logger.error("❌ Invalid signature - token has been tampered with")
            return None
        except InvalidTokenError as e:
            logger.error(f"❌ Invalid token: {e}")
            return None

    except Exception as e:
        logger.error(f"❌ Unexpected error decoding token: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None
