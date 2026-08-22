import uuid

from pydantic import BaseModel


class AppleSignInRequest(BaseModel):
    # The identity token from AuthenticationServices on iOS (a JWT), not the
    # authorization code.
    identity_token: str


class TokenResponse(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: uuid.UUID
    is_new_user: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str
    expires_in: int


class LogoutRequest(BaseModel):
    # GlobalSignOut is authorized by the caller's access token, not the refresh token.
    access_token: str
