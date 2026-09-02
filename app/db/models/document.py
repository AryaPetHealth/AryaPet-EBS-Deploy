import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pets.id", ondelete="SET NULL"), nullable=True
    )

    # S3 object key, e.g. "<user_id>/<uuid>-<filename>" (see documents.presign_upload).
    s3_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)

    status: Mapped[DocumentStatus] = mapped_column(
        # values_callable: SAEnum defaults to persisting the Python enum member's *name*
        # ("PENDING"), but the actual Postgres enum type only has the lowercase *values*
        # ("pending", ...) from the original migration - without this it fails with
        # InvalidTextRepresentationError on every insert.
        SAEnum(DocumentStatus, name="document_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    # Structured Textract output once parsed (see app/services/textract_parser.py).
    parsed_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
