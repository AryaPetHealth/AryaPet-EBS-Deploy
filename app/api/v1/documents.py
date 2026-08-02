import uuid

import boto3
from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser
from app.config import Settings, get_settings
from app.schemas.document import PresignedUploadRequest, PresignedUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])


# Note: route handlers below are sync `def`s (not `async def`) because they call boto3,
# which is blocking. FastAPI runs sync handlers in a threadpool automatically.


@router.post("/presign-upload", response_model=PresignedUploadResponse)
def presign_upload(
    payload: PresignedUploadRequest,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> PresignedUploadResponse:
    user_id = current_user["sub"]
    key = f"{user_id}/{uuid.uuid4()}-{payload.filename}"

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    upload_url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.documents_bucket, "Key": key, "ContentType": payload.content_type},
        ExpiresIn=300,
    )

    return PresignedUploadResponse(upload_url=upload_url, key=key)


@router.get("", response_model=list[str])
def list_documents(
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> list[str]:
    # Placeholder: no Document model/business logic yet; lists raw S3 keys under the
    # calling user's prefix.
    user_id = current_user["sub"]
    s3_client = boto3.client("s3", region_name=settings.aws_region)
    response = s3_client.list_objects_v2(Bucket=settings.documents_bucket, Prefix=f"{user_id}/")
    return [obj["Key"] for obj in response.get("Contents", [])]
