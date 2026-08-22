import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stable per-user identifier from Apple's identity token `sub` claim. Unique per
    # (Apple Developer Team ID + Services ID/Bundle ID), so it's stable across sign-ins
    # for this app but not shared with other apps.
    apple_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Cognito username we mint for this user (see app/auth/cognito_admin.py) — not
    # user-facing, just the key used to drive AdminInitiateAuth.
    cognito_username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Cognito's own internal user id — this is what shows up as the `sub` claim in the
    # JWTs Cognito issues, which is what every other route authenticates with via
    # CurrentUser. Distinct from cognito_username (which we chose) and from apple_sub
    # (Apple's identifier) — all three exist for different reasons.
    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Apple only returns email on the user's *first* sign-in ever (and it may be a
    # private relay address) — persist it then, since it may be absent on later logins.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # SNS platform endpoint ARN for push notifications (registered separately once a
    # device-registration endpoint exists). Nullable until that's built.
    sns_endpoint_arn: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
