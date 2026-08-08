"""Verifies Sign in with Apple identity tokens (the JWT the iOS app gets from
AuthenticationServices, sent to POST /v1/auth/apple).

This only verifies the token Apple issued to prove who the user is — it does not issue
any session token itself. Session tokens are minted by Cognito afterwards
(see app/auth/cognito_admin.py), so downstream routes keep validating a single kind of
token (Cognito's) via app/auth/dependencies.py.
"""

import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JOSEError

from app.config import Settings

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


class AppleTokenValidationError(Exception):
    pass


async def _fetch_jwks() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(APPLE_JWKS_URL)
        response.raise_for_status()
    return response.json()["keys"]


async def _get_jwks(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.monotonic()
    stale = now - _JWKS_CACHE["fetched_at"] > _JWKS_TTL_SECONDS
    if force_refresh or _JWKS_CACHE["keys"] is None or stale:
        _JWKS_CACHE["keys"] = await _fetch_jwks()
        _JWKS_CACHE["fetched_at"] = now
    return _JWKS_CACHE["keys"]


async def verify_apple_identity_token(token: str, settings: Settings) -> dict[str, Any]:
    """Returns Apple's verified claims (notably `sub` and, on first sign-in only, `email`)."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JOSEError as exc:
        raise AppleTokenValidationError("Invalid token header") from exc

    kid = unverified_header.get("kid")
    keys = await _get_jwks()
    key = next((k for k in keys if k["kid"] == kid), None)
    if key is None:
        keys = await _get_jwks(force_refresh=True)
        key = next((k for k in keys if k["kid"] == kid), None)
        if key is None:
            raise AppleTokenValidationError("Signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=APPLE_ISSUER,
            audience=settings.apple_bundle_id,
        )
    except JOSEError as exc:
        raise AppleTokenValidationError(str(exc)) from exc

    if not claims.get("sub"):
        raise AppleTokenValidationError("Token missing sub claim")

    return claims
