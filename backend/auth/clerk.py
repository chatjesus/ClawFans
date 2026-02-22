"""
Clerk JWT verification for FastAPI.
Verifies Bearer tokens issued by Clerk using their JWKS endpoint.
Falls back to "anonymous" when no token or invalid token is present.
"""
import logging
from typing import Optional

import httpx
from fastapi import Request
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# Simple in-process JWKS cache (keyed by issuer URL)
_jwks_cache: dict[str, dict] = {}


async def _fetch_jwks(iss: str) -> dict:
    """Fetch and cache JWKS from Clerk issuer."""
    jwks_url = f"{iss.rstrip('/')}/.well-known/jwks.json"
    if jwks_url not in _jwks_cache:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(jwks_url)
                resp.raise_for_status()
                _jwks_cache[jwks_url] = resp.json()
        except Exception as e:
            logger.warning(f"Could not fetch JWKS from {jwks_url}: {e}")
            return {}
    return _jwks_cache.get(jwks_url, {})


async def verify_clerk_token(token: str) -> Optional[str]:
    """
    Verify a Clerk JWT and return the user's Clerk user_id (sub claim).
    Returns None on failure.
    """
    try:
        unverified_claims = jwt.get_unverified_claims(token)
        iss = unverified_claims.get("iss", "")
        if not iss:
            return None

        jwks = await _fetch_jwks(iss)
        if not jwks:
            return None

        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        from jose import jwk as jose_jwk
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = jose_jwk.construct(k)
                break

        if not key:
            logger.debug(f"No matching JWK found for kid={kid}")
            return None

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims.get("sub")

    except JWTError as e:
        logger.debug(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.debug(f"Auth error: {e}")
        return None


async def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency: extract Clerk user_id from Authorization header.
    Returns the Clerk user_id if valid, or "anonymous" as fallback.
    This is intentionally permissive — endpoints choose whether to require auth.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "anonymous"

    token = auth[7:].strip()
    if not token:
        return "anonymous"

    user_id = await verify_clerk_token(token)
    return user_id or "anonymous"


def require_auth(user_id: str) -> str:
    """
    Use as a guard in endpoints that need a real user.
    Raises 401 if user is anonymous.
    """
    from fastapi import HTTPException
    if user_id == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
