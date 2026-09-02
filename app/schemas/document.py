import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.document import DocumentStatus


class PresignedUploadRequest(BaseModel):
    filename: str
    content_type: str
    pet_id: uuid.UUID | None = None


class PresignedUploadResponse(BaseModel):
    upload_url: str
    key: str
    document_id: uuid.UUID


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pet_id: uuid.UUID | None
    status: DocumentStatus
    parsed_result: dict | None
    failure_reason: str | None
    uploaded_at: datetime
    processed_at: datetime | None


class DocumentUploadStatus(BaseModel):
    document_id: uuid.UUID
    uploaded: bool
    size_bytes: int | None = None
    content_type: str | None = None


class DocumentTextSubmission(BaseModel):
    # OCR text extracted on-device by the client - see documents.submit_text.
    text: str
