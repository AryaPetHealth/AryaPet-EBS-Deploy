import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JOSEError

from app.auth.dev_token import DEV_ISSUER, get_dev_jwks
from app.config import Settings

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


class TokenValidationError(Exception):
    pass


def _jwks_url(settings: Settings) -> str:
    return (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )


def _issuer(settings: Settings) -> str:
    return f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/{settings.cognito_user_pool_id}"


async def _fetch_jwks(settings: Settings) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(_jwks_url(settings))
        response.raise_for_status()
    return response.json()["keys"]


async def get_jwks(settings: Settings, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.monotonic()
    stale = now - _JWKS_CACHE["fetched_at"] > _JWKS_TTL_SECONDS
    if force_refresh or _JWKS_CACHE["keys"] is None or stale:
        _JWKS_CACHE["keys"] = await _fetch_jwks(settings)
        _JWKS_CACHE["fetched_at"] = now
    return _JWKS_CACHE["keys"]


async def verify_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.get_unverified_claims(token)
    except JOSEError as exc:
        raise TokenValidationError("Invalid token header") from exc

    # Dev tokens (see app.auth.dev_token) are self-signed and only trusted when the
    # environment has explicitly opted in — this must never be true in prod.
    is_dev_token = settings.dev_auth_enabled and unverified_claims.get("iss") == DEV_ISSUER
    kid = unverified_header.get("kid")

    if is_dev_token:
        keys = get_dev_jwks()
        issuer = DEV_ISSUER
    else:
        keys = await get_jwks(settings)
        issuer = _issuer(settings)

    key = next((k for k in keys if k["kid"] == kid), None)
    if key is None and not is_dev_token:
        # Key may have rotated; refresh the cache once and retry before giving up.
        keys = await get_jwks(settings, force_refresh=True)
        key = next((k for k in keys if k["kid"] == kid), None)
    if key is None:
        raise TokenValidationError("Signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            # Cognito access tokens carry no `aud` claim (only id tokens do); audience is
            # checked manually below against the appropriate claim for each token type.
            options={"verify_aud": False},
        )
    except JOSEError as exc:
        raise TokenValidationError(str(exc)) from exc

    token_use = claims.get("token_use")
    if token_use == "id":
        if claims.get("aud") != settings.cognito_app_client_id:
            raise TokenValidationError("Invalid audience")
    elif token_use == "access":
        if claims.get("client_id") != settings.cognito_app_client_id:
            raise TokenValidationError("Invalid client_id")
    else:
        raise TokenValidationError("Unexpected token_use claim")

    return claims
