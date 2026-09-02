"""add pets.patient_id (human-readable id shown instead of the pet UUID)

Revision ID: b8961ac1310b
Revises: 82666b1e2733
Create Date: 2026-09-02

"""

import secrets
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8961ac1310b"
down_revision: Union[str, None] = "82666b1e2733"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors app/services/patient_id.py, kept independent on purpose - migrations
# shouldn't import app code that might change shape after this migration is written.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _generate_code(existing: set[str]) -> str:
    while True:
        code = "ARYA-C" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
        if code not in existing:
            existing.add(code)
            return code


def upgrade() -> None:
    op.add_column("pets", sa.Column("patient_id", sa.String(length=20), nullable=True))

    # Backfill any pre-existing rows before the column is made NOT NULL + unique below.
    conn = op.get_bind()
    existing_codes: set[str] = set()
    for row in conn.execute(sa.text("SELECT id FROM pets")):
        code = _generate_code(existing_codes)
        conn.execute(
            sa.text("UPDATE pets SET patient_id = :code WHERE id = :id"), {"code": code, "id": row.id}
        )

    op.alter_column("pets", "patient_id", existing_type=sa.String(length=20), nullable=False)
    op.create_index("ix_pets_patient_id", "pets", ["patient_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pets_patient_id", table_name="pets")
    op.drop_column("pets", "patient_id")
