"""Verifies Google Sign-In identity tokens (the JWT the app gets from the native
Google Sign-In SDK, sent to POST /v1/auth/google).

Mirrors app/auth/apple.py: this only verifies the token Google issued to prove who the
user is. Session tokens are still minted by Cognito afterwards (see
app/auth/cognito_admin.py), reusing the exact same ensure_cognito_user/sign_in_user
flow as Apple - Cognito only ever sees "a verified identity", not which IdP it came
from.
"""

import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JOSEError

from app.config import Settings

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
# Google ID tokens use either form depending on token version/library - accept both
# rather than relying on jose's single-issuer check.
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


class GoogleTokenValidationError(Exception):
    pass


async def _fetch_jwks() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(GOOGLE_JWKS_URL)
        response.raise_for_status()
    return response.json()["keys"]


async def _get_jwks(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.monotonic()
    stale = now - _JWKS_CACHE["fetched_at"] > _JWKS_TTL_SECONDS
    if force_refresh or _JWKS_CACHE["keys"] is None or stale:
        _JWKS_CACHE["keys"] = await _fetch_jwks()
        _JWKS_CACHE["fetched_at"] = now
    return _JWKS_CACHE["keys"]


async def verify_google_identity_token(token: str, settings: Settings) -> dict[str, Any]:
    """Returns Google's verified claims (notably `sub` and `email`)."""
    if not settings.google_client_id:
        raise GoogleTokenValidationError("Google sign-in is not configured on this backend")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JOSEError as exc:
        raise GoogleTokenValidationError("Invalid token header") from exc

    kid = unverified_header.get("kid")
    keys = await _get_jwks()
    key = next((k for k in keys if k["kid"] == kid), None)
    if key is None:
        keys = await _get_jwks(force_refresh=True)
        key = next((k for k in keys if k["kid"] == kid), None)
        if key is None:
            raise GoogleTokenValidationError("Signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"verify_iss": False},  # checked manually below - see GOOGLE_ISSUERS
        )
    except JOSEError as exc:
        raise GoogleTokenValidationError(str(exc)) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenValidationError("Unexpected token issuer")

    if not claims.get("sub"):
        raise GoogleTokenValidationError("Token missing sub claim")

    return claims
