from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.cognito import TokenValidationError, verify_token
from app.config import Settings, get_settings

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
