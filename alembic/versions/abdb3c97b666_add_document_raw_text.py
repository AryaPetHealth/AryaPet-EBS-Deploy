"""add documents.raw_text (client-submitted OCR text)

Revision ID: abdb3c97b666
Revises: b8961ac1310b
Create Date: 2026-09-02

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abdb3c97b666"
down_revision: Union[str, None] = "b8961ac1310b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("raw_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "raw_text")
