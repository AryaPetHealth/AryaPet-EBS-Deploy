"""Long-polls the processing SQS queue and runs Textract on uploaded documents.

Runs as a standalone process on the same EB SingleInstance environment as the API
(e.g. as a second supervisord program), not inside the FastAPI event loop. Messages that
raise are left on the queue for SQS's built-in redrive to the `-dlq` queue after
maxReceiveCount is exceeded.
"""

import json
import logging
from typing import Any

import boto3

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

WAIT_TIME_SECONDS = 20
MAX_MESSAGES = 10
VISIBILITY_TIMEOUT = 120


def handle_message(
    message: dict[str, Any], textract_client: Any, sns_client: Any, settings: Settings
) -> None:
    body = json.loads(message["Body"])
    # TODO: parse the S3 event notification in `body`, call textract_client to analyze the
    # document, then publish the result via sns_client.
    logger.info("Received processing message: %s", body)


def run() -> None:
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)
    textract = boto3.client("textract", region_name=settings.aws_region)
    sns = boto3.client("sns", region_name=settings.aws_region)

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
                handle_message(message, textract, sns, settings)
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
    run()
