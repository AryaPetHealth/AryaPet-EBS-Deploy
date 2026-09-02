"""Self-signed JWT issuer for local/dev testing, decoupled from Cognito and Apple.

Lets a developer get a valid bearer token for Swagger's Authorize button (or curl)
without doing a full Sign in with Apple + Cognito round trip. Only reachable when
Settings.dev_auth_enabled is set (see the /v1/auth/dev-token route) — that flag must
never be true outside local/dev, since a token minted here bypasses Cognito and
Apple's identity checks entirely.
"""

import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

DEV_ISSUER = "urn:arya:dev-auth"
_KID = "dev-auth-key-1"

# Generated once per process rather than persisted, since this is a testing aid with
# no continuity requirement — a dev token minted before a restart simply won't verify
# after one.
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
_PUBLIC_PEM = _PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
_PUBLIC_JWK = jwk.RSAKey(_PUBLIC_PEM, algorithm="RS256").to_dict()
_PUBLIC_JWK.update(kid=_KID, use="sig", alg="RS256")


def get_dev_jwks() -> list[dict[str, Any]]:
    return [_PUBLIC_JWK]


def mint_dev_token(*, cognito_sub: str, client_id: str, token_use: str, expires_in: int = 3600) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": cognito_sub,
        "iss": DEV_ISSUER,
        "token_use": token_use,
        "iat": now,
        "exp": now + expires_in,
    }
    # Mirrors how real Cognito tokens carry the client id: id tokens as `aud`,
    # access tokens as `client_id` (see cognito.verify_token).
    if token_use == "id":
        claims["aud"] = client_id
    else:
        claims["client_id"] = client_id

    return jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": _KID})
