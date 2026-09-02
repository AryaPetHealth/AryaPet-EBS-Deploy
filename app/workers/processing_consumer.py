"""Long-polls the processing SQS queue and runs Textract on uploaded documents.

Runs as a standalone process on the same EB SingleInstance environment as the API
(e.g. as a second supervisord program), not inside the FastAPI event loop. Messages that
raise are left on the queue for SQS's built-in redrive to the `-dlq` queue after
maxReceiveCount is exceeded.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote_plus

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import build_database_url, get_settings
from app.db.models.document import Document, DocumentStatus
from app.db.session import get_session_maker, init_engine
from app.services.document_classifier import build_document_card, extract_text_and_tables

logger = logging.getLogger(__name__)

WAIT_TIME_SECONDS = 20
MAX_MESSAGES = 10
VISIBILITY_TIMEOUT = 120


async def _process_document(
    bucket: str,
    key: str,
    textract_client: Any,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        result = await session.execute(select(Document).where(Document.s3_key == key))
        document = result.scalar_one_or_none()
        if document is None:
            # Nothing to retry - the Document row is created before the upload happens,
            # so a missing row here means the key doesn't belong to any known upload.
            logger.warning("No Document row found for s3_key=%s; skipping", key)
            return

        try:
            response = textract_client.analyze_document(
                Document={"S3Object": {"Bucket": bucket, "Name": key}},
                FeatureTypes=["TABLES", "FORMS"],
            )
            text, tables = extract_text_and_tables(response)
            card = build_document_card(text, tables)
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.failure_reason = str(exc)
            await session.commit()
            raise

        document.status = DocumentStatus.COMPLETED
        document.parsed_result = card
        document.processed_at = datetime.now(UTC)
        await session.commit()


async def handle_message(
    message: dict[str, Any],
    textract_client: Any,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    body = json.loads(message["Body"])
    for record in body.get("Records", []):
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        raw_key = s3_info.get("object", {}).get("key")
        if not bucket or not raw_key:
            logger.warning("Skipping record with missing bucket/key: %s", record)
            continue

        # S3 event notifications URL-encode the key (e.g. spaces as '+').
        key = unquote_plus(raw_key)
        await _process_document(bucket, key, textract_client, session_maker)


async def run() -> None:
    settings = get_settings()
    init_engine(
        build_database_url(settings),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    session_maker = get_session_maker()

    sqs = boto3.client("sqs", region_name=settings.aws_region)
    textract = boto3.client("textract", region_name=settings.aws_region)

    logger.info("Starting processing consumer on %s", settings.sqs_processing_queue_url)

    while True:
        response = sqs.receive_message(
            QueueUrl=settings.sqs_processing_queue_url,
            MaxNumberOfMessages=MAX_MESSAGES,
            WaitTimeSeconds=WAIT_TIME_SECONDS,
            VisibilityTimeout=VISIBILITY_TIMEOUT,
        )

        for message in response.get("Messages", []):
            try:
                await handle_message(message, textract, session_maker)
            except Exception:
                logger.exception(
                    "Failed to process message %s; leaving for redrive", message.get("MessageId")
                )
                continue

            sqs.delete_message(
                QueueUrl=settings.sqs_processing_queue_url, ReceiptHandle=message["ReceiptHandle"]
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
