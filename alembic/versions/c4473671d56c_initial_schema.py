"""initial schema: users, pets, documents

Revision ID: c4473671d56c
Revises:
Create Date: 2026-08-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4473671d56c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("apple_sub", sa.String(length=255), nullable=False),
        sa.Column("cognito_username", sa.String(length=255), nullable=False),
        sa.Column("cognito_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("sns_endpoint_arn", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_apple_sub", "users", ["apple_sub"], unique=True)
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.create_unique_constraint("uq_users_cognito_username", "users", ["cognito_username"])

    op.create_table(
        "pets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("species", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"])

    document_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed", name="document_status"
    )
    document_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("status", document_status, nullable=False, server_default="pending"),
        sa.Column("parsed_result", postgresql.JSONB(), nullable=True),
        sa.Column("failure_reason", sa.String(length=1024), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_unique_constraint("uq_documents_s3_key", "documents", ["s3_key"])


def downgrade() -> None:
    op.drop_table("documents")
    postgresql.ENUM(name="document_status").drop(op.get_bind(), checkfirst=True)
    op.drop_table("pets")
    op.drop_table("users")
