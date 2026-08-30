"""add google_sub, make apple_sub nullable

Revision ID: 82666b1e2733
Revises: c4473671d56c
Create Date: 2026-08-30

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82666b1e2733"
down_revision: Union[str, None] = "c4473671d56c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "apple_sub", existing_type=sa.String(length=255), nullable=True)

    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")

    op.alter_column("users", "apple_sub", existing_type=sa.String(length=255), nullable=False)
