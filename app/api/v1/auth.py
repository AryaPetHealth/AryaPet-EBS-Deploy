"""Login/signup for the app. There is a single endpoint for both — Sign in with Apple
is idempotent, so the first call for a given Apple account creates the user (signup)
and every call after that is a login. See app/auth/cognito_admin.py for why Cognito
Admin APIs are used instead of Cognito's own federated-IdP support.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.apple import AppleTokenValidationError, verify_apple_identity_token
from app.auth.cognito_admin import (
    CognitoAdminError,
    ensure_cognito_user,
    global_sign_out,
    refresh_tokens,
    sign_in_user,
)
from app.config import Settings, get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AppleSignInRequest, LogoutRequest, RefreshRequest, RefreshResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _cognito_username_for(apple_sub: str) -> str:
    return f"apple_{apple_sub}"


@router.post("/apple", response_model=TokenResponse)
async def sign_in_with_apple(
    payload: AppleSignInRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        claims = await verify_apple_identity_token(payload.identity_token, settings)
    except AppleTokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    apple_sub = claims["sub"]
    email = claims.get("email")
    now = datetime.now(UTC)

    result = await db.execute(select(User).where(User.apple_sub == apple_sub))
    user = result.scalar_one_or_none()
    is_new_user = user is None

    if user is None:
        cognito_username = _cognito_username_for(apple_sub)
        try:
            cognito_sub = await asyncio.to_thread(
                ensure_cognito_user, cognito_username, email=email, settings=settings
            )
        except CognitoAdminError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        user = User(
            apple_sub=apple_sub,
            cognito_username=cognito_username,
            cognito_sub=cognito_sub,
            email=email,
            last_login_at=now,
        )
        db.add(user)
        await db.flush()  # assigns user.id without committing yet
    else:
        user.last_login_at = now
        if email and not user.email:
            # Apple only sends email on the very first sign-in; capture it if we
            # somehow missed it (e.g. the row was created before this field existed).
            user.email = email

    try:
        tokens = await asyncio.to_thread(sign_in_user, user.cognito_username, settings)
    except CognitoAdminError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    await db.commit()

    return TokenResponse(
        id_token=tokens.id_token,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user_id=user.id,
        is_new_user=is_new_user,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    payload: RefreshRequest,
    settings: Settings = Depends(get_settings),
) -> RefreshResponse:
    try:
        tokens = await asyncio.to_thread(refresh_tokens, payload.refresh_token, settings)
    except CognitoAdminError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return RefreshResponse(
        id_token=tokens.id_token,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        await asyncio.to_thread(global_sign_out, payload.access_token, settings)
    except CognitoAdminError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
