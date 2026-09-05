import uuid

from pydantic import BaseModel


class AppleSignInRequest(BaseModel):
    # The identity token from AuthenticationServices on iOS (a JWT), not the
    # authorization code.
    identity_token: str

    # Apple sends these to the client only on that identity's first authorization
    # ever, straight from the native credential (not the identity token) — the
    # client forwards them here so the backend can persist them. Absent on every
    # later sign-in, so only used to backfill a user row that doesn't have a name yet.
    first_name: str | None = None
    last_name: str | None = None


class GoogleSignInRequest(BaseModel):
    # The ID token from the native Google Sign-In SDK (a JWT).
    identity_token: str

    first_name: str | None = None
    last_name: str | None = None


class DevTokenRequest(BaseModel):
    # Identifies a stable dev/test user across calls (e.g. "tester1") — repeated calls
    # with the same subject return tokens for the same underlying User row.
    subject: str = "dev-user"
    email: str | None = None


class TokenResponse(BaseModel):
    id_token: str
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: uuid.UUID
    is_new_user: bool

    # The canonical, currently-stored values for this user — always returned
    # regardless of whether this particular sign-in call supplied new ones, so a
    # different/reinstalled client can hydrate its local profile from here instead
    # of relying on Apple/Google resending them (which only happens once, ever).
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None


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
