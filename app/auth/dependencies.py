from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cognito import TokenValidationError, verify_token
from app.config import Settings, get_settings
from app.db.models.user import User
from app.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        claims = await verify_token(credentials.credentials, settings)
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return claims


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def get_current_db_user(
    claims: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolves the validated JWT's `sub` claim (Cognito's internal user id) to our
    own User row. Routes should depend on this — not raw JWT claims — whenever they
    need the app's internal user id (e.g. to scope a query by owner_id), since the
    JWT's `sub` is Cognito's id, not ours (see User.cognito_sub for why both exist)."""
    cognito_sub = claims.get("sub")
    result = await db.execute(select(User).where(User.cognito_sub == cognito_sub))
    user = result.scalar_one_or_none()
    if user is None:
        # Shouldn't happen for a token we just validated as genuinely Cognito-issued —
        # would mean the user row was deleted after the token was issued.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentDbUser = Annotated[User, Depends(get_current_db_user)]
