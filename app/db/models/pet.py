import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.patient_id import generate_patient_id


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Human-readable identifier shown to users/clinicians in the API and Swagger
    # instead of the internal UUID `id` above (e.g. "ARYA-C7K2M9"). `id` stays the
    # actual primary key/FK target (see Document.pet_id) so this can't collide with
    # anything else in the schema.
    patient_id: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False, default=generate_patient_id
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str] = mapped_column(String(60), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
