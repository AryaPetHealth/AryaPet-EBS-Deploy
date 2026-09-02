"""Long-polls the processing SQS queue and classifies/extracts info from documents
whose OCR text the client has already submitted (see documents.submit_text).

Runs as a standalone process on the same EB SingleInstance environment as the API
(e.g. as a second supervisord program), not inside the FastAPI event loop. Messages that
raise are left on the queue for SQS's built-in redrive to the `-dlq` queue after
maxReceiveCount is exceeded.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import build_database_url, get_settings
from app.db.models.document import Document, DocumentStatus
from app.db.session import get_session_maker, init_engine
from app.services.document_classifier import build_document_card

logger = logging.getLogger(__name__)

WAIT_TIME_SECONDS = 20
MAX_MESSAGES = 10
VISIBILITY_TIMEOUT = 120


async def _process_document(
    document_id: uuid.UUID,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        document = await session.get(Document, document_id)
        if document is None:
            logger.warning("No Document row found for id=%s; skipping", document_id)
            return

        try:
            card = build_document_card(document.raw_text or "")
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
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    body = json.loads(message["Body"])
    document_id = body.get("document_id")
    if not document_id:
        logger.warning("Skipping message with no document_id: %s", body)
        return

    await _process_document(uuid.UUID(document_id), session_maker)


async def run() -> None:
    settings = get_settings()
    init_engine(
        build_database_url(settings),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    session_maker = get_session_maker()

    sqs = boto3.client("sqs", region_name=settings.aws_region)

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
                await handle_message(message, session_maker)
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
