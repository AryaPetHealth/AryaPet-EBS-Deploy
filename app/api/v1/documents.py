import uuid

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentDbUser
from app.config import Settings, get_settings
from app.db.models.document import Document
from app.db.models.pet import Pet
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.document import (
    DocumentRead,
    DocumentUploadStatus,
    PresignedUploadRequest,
    PresignedUploadResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/presign-upload", response_model=PresignedUploadResponse)
async def presign_upload(
    payload: PresignedUploadRequest,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PresignedUploadResponse:
    if payload.pet_id is not None:
        # Prevent attaching a document to a pet the caller doesn't own.
        pet = await db.get(Pet, payload.pet_id)
        if pet is None or pet.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

    key = f"{current_user.id}/{uuid.uuid4()}-{payload.filename}"

    # generate_presigned_url is a local signing computation, not a network call, so
    # it's safe to call directly from an async def without a threadpool hop.
    s3_client = boto3.client("s3", region_name=settings.aws_region)
    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.documents_bucket, "Key": key, "ContentType": payload.content_type},
        ExpiresIn=300,
    )

    document = Document(owner_id=current_user.id, pet_id=payload.pet_id, s3_key=key)
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return PresignedUploadResponse(upload_url=upload_url, key=key, document_id=document.id)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.owner_id == current_user.id).order_by(Document.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def _get_owned_document(document_id: uuid.UUID, current_user: User, db: AsyncSession) -> Document:
    document = await db.get(Document, document_id)
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Document:
    return await _get_owned_document(document_id, current_user, db)


@router.get("/{document_id}/upload-status", response_model=DocumentUploadStatus)
async def get_upload_status(
    document_id: uuid.UUID,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadStatus:
    # The Document row is created when the presigned URL is issued, before the client has
    # actually PUT the file to S3 — so the DB alone can't say whether the upload happened.
    # This checks the bucket directly.
    document = await _get_owned_document(document_id, current_user, db)

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    try:
        head = s3_client.head_object(Bucket=settings.documents_bucket, Key=document.s3_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return DocumentUploadStatus(document_id=document.id, uploaded=False)
        raise

    return DocumentUploadStatus(
        document_id=document.id,
        uploaded=True,
        size_bytes=head.get("ContentLength"),
        content_type=head.get("ContentType"),
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    # Removes the DB row only — the underlying S3 object is left in place (cleanup is a
    # follow-up, e.g. an S3 lifecycle rule or a periodic reconciliation job).
    document = await _get_owned_document(document_id, current_user, db)
    await db.delete(document)
    await db.commit()
